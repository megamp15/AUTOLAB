---
tags: [gitops, tenancy, tailscale, opentofu, ansible]
status: alpha
audience: operator
---

# Tenants

A tenant is a stack whose VMs belong to someone else. The hypervisor, the
modules, the workflows and the Builder baseline are the provider's; the VMs
enrol on the tenant's tailnet and from that moment the tenant reaches them
the way it reaches any of its own machines. The provider hands out running
Linux boxes and keeps root on the hosts underneath. That is the whole
arrangement, and it is the same one a cloud provider makes.

## Two planes

Every VM sits on two networks, and tenancy is the point where they have to be
told apart.

| Plane | Network | Whose | Carries |
|---|---|---|---|
| **Management** | `vmbr1`, the node's private `10.42.0.0/24` | Provider | Builder SSH through the hypervisor; later, backups and provider-side monitoring |
| **Access** | The VM's tailnet | Tenant | Tailscale SSH for the tenant's people and CI, the tenant's services |

The provider's own VMs have never needed the distinction because one tailnet
served both roles. A tenant VM is on a tailnet the CI runner is not on, so
the Builder cannot dial it by name. It dials the hypervisor instead — already
reachable as `tag:autolab-pve` — and hops onto the bridge:

```
CI runner ──provider tailnet──▶ xps-pve ──ProxyJump, vmbr1──▶ 10.42.0.201
```

Two things follow. Tenant VMs need **declared addresses** (`ipv4_address`
as a CIDR plus `ipv4_gateway`), because a leased one is unknowable at plan
time and the plan is where the inventory comes from. And the Builder needs a
**key**, because on the bridge it talks to plain `sshd` and Tailscale SSH is
not there to vouch for it. The stack injects the firewall rule that lets the
hypervisor in on port 22; a tenant cannot omit it and lock the baseline out.

## What the tenant provides

Three things, none of which give the provider anything beyond the ability to
put VMs on the tenant's network.

1. **A tag** in the tenant's tailnet policy, with an `ssh` rule for whoever
   should reach the VMs. `accept` for their CI runner, `check` for people —
   CI cannot answer a browser re-auth.

   ```jsonc
   "tagOwners": { "tag:qnta-vm": ["autogroup:admin"] },
   "ssh": [
     { "action": "accept", "src": ["autogroup:member", "tag:ci"],
       "dst": ["tag:qnta-vm"], "users": ["autogroup:nonroot", "root"] },
   ],
   ```

2. **An OAuth client** from that tailnet (Settings → Trust credentials),
   scoped to exactly what the two stack hooks need and nothing else:

   | Scope | Access | Tag |
   |---|---|---|
   | Auth Keys | Write | the tag above |
   | Devices → Core | Write | — |

   `auth_keys` lets OpenTofu mint a join key per apply. `devices:core` lets
   the destroy-time hook delete the device record. The client cannot read
   the tenant's policy, change it, or touch a device it did not create.

3. **The LAN ports its workloads need** between VMs, declared in each
   machine's `builder.firewall_rules`. Swarm wants 2377/tcp, 7946/tcp+udp,
   4789/udp from the bridge. Declared there rather than punched by hand, or
   the next baseline run closes them again.

## Wiring a tenant

Once, per tenant. `qnta` is the worked example.

1. **GitHub Environment** named after the stack (Settings → Environments →
   `qnta`), holding the tenant's OAuth client under the *same names* the
   provider uses — `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET`
   — and the variable `TAILSCALE_VM_TAG=tag:qnta-vm`. Environment secrets
   shadow repository secrets, which is the entire mechanism: the workflows
   do not change, the environment decides which tailnet they enrol into.

2. **The Builder keypair**, once for all tenants. Provider-owned.

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/autolab-builder -N '' -C autolab-builder
   gh secret set BUILDER_SSH_PRIVATE_KEY < ~/.ssh/autolab-builder
   gh variable set BUILDER_SSH_PUBLIC_KEY --body "$(cat ~/.ssh/autolab-builder.pub)"
   ```

   cloud-init places the public half on the break-glass user of tenant VMs
   so the very first Builder run can get in. The `gitops-user` role then
   installs it for `gitops`, on every stack, as an authoritative list:
   remove the variable and the next baseline run removes the key.

3. **The stack**: `infra/stacks/<tenant>/` with `tenant = "<name>"` in its
   `machines.auto.tfvars`, static addresses from `.201` upward (last octet
   equal to the VMID), `common_tags` including `tenant-<name>`, and
   `observability = { agent = false }` until provider-side monitoring runs
   over the bridge. Add the stack name to the `environment` choice in
   workflows 03, 04, 05 and 99.

## Running it

Same workflows, one input.

| Step | Workflow | Inputs |
|---|---|---|
| Create the VMs | `04 - OpenTofu Apply` | `environment: qnta`, `confirm: apply` |
| First baseline | `05 - Ansible Builder` | `environment: qnta`, `playbook: harden`, `bootstrap: true`, `confirm: apply` |
| Every later run | `05 - Ansible Builder` | `environment: qnta`, any playbook, `bootstrap: false` |
| Remove them | `99 - OpenTofu Destroy` | `environment: qnta`, `confirm: DESTROY` |

After apply the VMs appear in the tenant's admin console under their tag,
and the tenant's people can `ssh qnta-mgmt` from any device on that tailnet.
Nothing on the provider's tailnet can see them, and nothing on the tenant's
tailnet can see the hypervisor.

## What the tenant does after

Everything from `docker swarm init` up: swarm, stacks, registries, tunnels,
internal proxies, application deploys, database migrations. Their repo keeps
its operating two-thirds and loses its provisioning third — Packer, the VM
resources, the Tailscale join — because those are now the provider's.

## Not covered yet

- **NAS storage.** Tenant VMs on a NAT bridge reach the NAS over the LAN but
  all arrive as the node's address, so an NFS export scoped to the node is
  open to every VM on it — the per-host scoping `nfs.yml` relies on is lost.
  Two ways out: SMB with a per-tenant NAS user (credential-based, so the
  shared source address stops mattering), or the bridge becoming a real LAN
  segment when the second node lands, after which tenant VMs have their own
  addresses and the business's current per-host NFS exports carry over
  unchanged. Either way, live databases stay on the VM's own disk and only
  their dumps go to the NAS.
- **Provider-side monitoring.** The agent ships to `jwst` by tailnet name.
  Tenant VMs opt out until the stack reaches them over the bridge.
- **Backups.** PBS is the next phase and belongs on the management plane;
  tenant guests are backed up like any other, under a PBS namespace per
  tenant.

## Things that will mislead you

- **A tenant VM does not answer `tailscale ping` from the runner, and that is
  correct.** The readiness gate pings the hypervisor for tenant hosts. If the
  gate reports the *VM* unreachable over Tailscale, the inventory rendered it
  without a jump host — check `ssh_jump_host` in `tofu output builder_machines`.
- **`ansible_ssh_common_args` in the inventory replaces `ANSIBLE_SSH_COMMON_ARGS`;
  it does not add to it.** The generator restates `StrictHostKeyChecking=yes`
  for tenant hosts for that reason. Drop it and host-key checking silently
  turns off for exactly the hosts reached over an intermediate box.
- **Changing `BUILDER_SSH_PUBLIC_KEY` rebuilds tenant VMs.** It is in
  cloud-init user-data, and a changed snippet replaces the VM. Rotating the
  Builder key is a Builder-time change (the `gitops-user` role) — set the new
  public key, run `harden`, then swap the private half. Leave the cloud-init
  copy alone until the VM is rebuilt for some other reason.
- **The agent-not-reporting alert excludes tenant guests by tag, not by
  name.** The lab's inventory never sees them, so name-based opt-out cannot.
  A tenant stack without `tenant-<name>` in `common_tags` fires that alert
  forever for VMs behaving exactly as declared.
