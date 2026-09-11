# Autolab Ansible Builder

Phase 2C configures Linux hosts after they exist. Current Builder targets are
cloud-init-capable Proxmox VMs. LXC Builder targets are deferred until they
meet the same reachable-host contract; future provider-neutral reachable Linux
hosts, including VPS hosts, remain intended. Once SSH is reachable, the builder
should apply the same server baseline.

## Scope

This scaffold is intentionally provider-neutral:

- Proxmox-specific work stays in `docs/proxmox/`, `infra/stacks/`, and
  `infra/packer/`.
- VPS-specific work belongs in future provider stacks under `infra/`.
- Shared Linux configuration belongs here as Ansible roles.

## Configuration layers

Every Builder VM receives the universal baseline: Debian package policy, a
dedicated `gitops` automation user, named operator accounts, SSH hardening,
root SSH disabled, and a default-deny UFW policy with management allowed over
`tailscale0`. Builder transport is Tailscale SSH: cloud-init enables the host
feature after the VM has enrolled, and CI reaches the VM using its short-lived
GitHub OIDC/WIF identity as `tag:ci-runner` and the tailnet policy.

Environment inventories may set environment-wide values. Per-machine
exceptions live beside the VM in `infra/stacks/<environment>/machines.auto.tfvars`:

```hcl
builder = {
  firewall_rules = [{ port = 443, protocol = "tcp", source = "100.64.0.0/10" }]
  docker_enabled = true
}
```

No port is exposed unless that machine declares it. OpenTofu emits this
non-sensitive policy as `builder_machines`; `scripts/generate-ansible-inventory.py`
turns it into an ignored JSON inventory using each VM's MagicDNS hostname.
The generated inventory step rejects malformed `builder_machines` output. A
Builder run also stops during inventory preparation when there are no enabled
Builder Machines, before Ansible starts.

## Layout

```text
builders/ansible/
  ansible.cfg
  inventories/
    lab/
      hosts.example.yml
    vps/
      hosts.example.yml
  playbooks/
    harden.yml
    docker.yml
    tailscale-update.yml
  roles/
    base-linux/
    ssh-hardening/
    firewall/
    tailscale-update/
    gitops-user/
    admin-users/
    docker-host/
```

## First run

Copy an example inventory and replace the placeholder host values:

```bash
tofu -chdir=infra/stacks/lab output -json builder_machines > /tmp/builder-machines.json
python3 scripts/generate-ansible-inventory.py /tmp/builder-machines.json \
  --output /tmp/autolab-inventory.json --user autolab
cd builders/ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i /tmp/autolab-inventory.json playbooks/harden.yml
```

The first run uses `autolab`; later runs generate the same inventory with
`--user gitops`. Before either run, configure the tailnet policy for the
`tag:ci-runner` to reach `tag:autolab-vm` and permit SSH for `autolab` during
bootstrap and `gitops` afterward; never permit `root`. Do not add a VM SSH
key; the PVE SSH key is only for the Proxmox bastion.
Do not commit inventories, private keys, or auth keys.

## Three identities, three jobs

A Builder VM ends up with three kinds of account, and they are deliberately not
interchangeable:

| Account | Created by | SSH key | Purpose |
|---|---|---|---|
| `autolab` | cloud-init, first boot | yes — `identity_defaults.ssh_public_keys` | Bootstrap and break-glass. The only way in if Tailscale itself is broken, so it stays untouched otherwise. |
| `gitops` | `gitops-user` role | no | CI's automation identity. Workflow **05 - Ansible Builder** is the only thing that uses it. |
| operators (e.g. `megamp15`) | `admin-users` role | no | Interactive human work, over Tailscale SSH. |

Humans get their own accounts so interactive sessions never share state with
CI: shell history, dotfiles, and half-finished changes stay out of the account
automation depends on, and `autolab` stays clean for recovery. Escalation is
`sudo`, which attributes the action to a named user — root login is disabled
and the tailnet policy must never grant `root`.

Operators are listed in `playbooks/harden.yml` under `autolab_admin_users`, and
the username should be the local-part of the operator's tailnet login
(`megamp15@github` becomes `megamp15`) so it matches the `users` list in the
tailnet SSH policy.

Tailscale SSH **will not create these accounts** — it only uses accounts that
already exist on the host. A tailnet policy granting `megamp15` is inert until
`harden.yml` has run. This is also why operator accounts are provisioned by
Ansible rather than cloud-init: cloud-init runs only on first boot, and editing
its user-data churns the snippet and force-replaces the VM.

### Onboarding and offboarding an operator

Both directions are a git change plus a tailnet policy change, applied by
re-running **05 - Ansible Builder**. Neither half works alone.

To onboard, add them to `autolab_admin_users` in `playbooks/harden.yml` and add
the username to the `users` list of the human-access rule in the tailnet policy.

To offboard, move them to `autolab_admin_users_absent` and remove them from
that same `users` list:

```yaml
autolab_admin_users:
  - name: megamp15

autolab_admin_users_absent:
  - name: former-operator
```

Removal is an explicit list rather than an inferred sweep of "any sudo account
not listed above" — an inferred sweep would delete `gitops`, `autolab`, and
distro accounts the first time a variable failed to load. The role refuses to
run if a name appears in both lists.

The role revokes sudo before deleting the account, so an interrupted run cannot
leave an account holding passwordless root through a stale sudoers file, and it
removes the home directory so nothing survives to be inherited by UID reuse.

Leave the entry in `autolab_admin_users_absent` until every Builder target has
had `harden.yml` applied; a VM that was offline for the run still has the
account. Removing the entry too early makes the deletion silently skip that
host.

See [01 - Tailscale SSH](../../docs/gitops/01-tailscale-ssh.md) for the policy
side.

## Baseline contract

The `harden.yml` playbook is the common baseline every managed server receives:

- package cache refresh and security update policy
- non-root admin user
- separate `gitops` deploy user
- named human operator accounts (`admin-users`)
- root/password SSH disabled
- firewall defaults
- Tailscale/private management firewall access
- Tailscale SSH transport (cloud-init installs/enables it after enrollment;
  tailnet policy grants CI access)

`docker.yml` remains an opt-in playbook. `tailscale-update.yml` is security
maintenance: it upgrades Tailscale to the current stable release via the
official `pkgs.tailscale.com` apt repo. Run it periodically (or after a
Tailscale security advisory); join and enrollment stay owned by cloud-init,
so this playbook never touches auth keys or `tailscale up`. Tailscale SSH is
not an optional
playbook or per-machine flag; it is the approved Builder transport. Do not
use Tailscale SSH check mode `always` for the `gitops` automation identity.

Workflow **05 - Ansible Builder** performs the bootstrap `autolab` run. After
the baseline creates `gitops`, regular Builder runs use `gitops`; run Docker
only after the baseline is healthy.
