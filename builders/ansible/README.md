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
dedicated `gitops` automation user, SSH hardening, root SSH disabled, and a
default-deny UFW policy with management allowed over `tailscale0`. Builder
transport is Tailscale SSH: cloud-init enables the host feature after the VM
has enrolled, and CI reaches the VM using its short-lived GitHub OIDC/WIF
identity as `tag:ci-runner` and the tailnet policy.

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

## Baseline contract

The `harden.yml` playbook is the common baseline every managed server receives:

- package cache refresh and security update policy
- non-root admin user
- separate `gitops` deploy user
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
