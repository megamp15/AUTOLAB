---
name: tenant
description: Run someone else's VMs on AUTOLAB's hypervisors as a tenant - their own Stack, their own tailnet, the provider's baseline. Use to wire a new tenant, add or remove a tenant's VMs, or when a tenant machine cannot be reached.
---

# A tenant

The model, the two planes and every trap: `docs/gitops/tenants.md`. The
provider owns everything from the VM down, the tenant from the VM up.
`qnta` is the worked example.

## Wiring a new tenant

By hand, by the user, once:

1. A GitHub Environment named for the Stack, holding the tenant's tailnet
   OAuth client under the provider's own secret names
   (`TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET`) and the
   variable `TAILSCALE_VM_TAG`. Environment values shadow the repository's:
   that is the whole mechanism. `secret`.

Code:

2. `infra/stacks/<tenant>/` from `infra/stacks/_template`, with
   `tenant = "<name>"`, static addresses from `.201` up (last octet equal
   to the VMID), `common_tags` including `tenant-<name>`.
3. The Stack's name in the `environment` choices of `03`, `04`, `05`, `99`.
4. `pull-request`.

## Running it

`run-workflow`, with `environment=<tenant>` on every run:

| step | run |
|---|---|
| create the VMs | `03`, then `04` |
| first baseline | `05` `harden`, `bootstrap=true` |
| NAS | `05` `storage` (SMB: a credential per tenant, `nas`) |
| later | `05`, any playbook, `bootstrap=false` |

The Builder reaches tenant VMs over the node's private bridge, through the
node, with the Builder keypair. It never joins the tenant's tailnet.

## Proof

- The VMs appear in the tenant's admin console under their tag, and the
  tenant's people reach them there.
- From the provider's tailnet they do not answer; from the tenant's, the
  hypervisor does not.

## Monitoring

Provider-side, over the bridge: `docs/gitops/tenants.md`, "Monitoring", and
`observe`.

## When a tenant machine cannot be reached

| symptom | cause |
|---|---|
| the readiness gate says the VM is unreachable over Tailscale | the inventory rendered it without a jump host: check `ssh_jump_host` in the Stack's `builder_machines` output |
| an agent on the bridge reports nothing | ufw on the stack host, ports `9009` and `3101` from the bridge |
| VMs rebuilt after a key change | `BUILDER_SSH_PUBLIC_KEY` is in cloud-init: rotate it through `harden`, not by changing the variable first |

## Guardrails

- Removing a tenant is `99` for that Stack: `confirm=DESTROY`, on the
  user's explicit word naming the tenant.
- What runs inside a tenant's VMs (swarm, stacks, tunnels) is theirs and is
  not managed from here.
