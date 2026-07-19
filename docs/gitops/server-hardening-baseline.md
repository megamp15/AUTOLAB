---
tags: [gitops, security, hardening, ssh, tailscale]
status: draft
audience: operator
---

# Server hardening baseline

Every Autolab VM, supported LXC, or VPS should eventually meet the same security
baseline. This doc separates **what ships today** from **what phase 2C Ansible
will enforce later**.

## Implemented today (phase 2A — cloud-init only)

When OpenTofu clones a `builder_target` VM, the `cloud-init` module
(`infra/modules/cloud-init/`) injects on first boot:

| Control | Status today |
|---------|----------------|
| Admin user (`autolab` by default) | Yes — created via cloud-init |
| SSH public keys only for admin user | Yes — from `identity_defaults.ssh_public_keys` in local `terraform.tfvars` |
| Password login for admin user | Locked (`lock_passwd: true`) |
| qemu-guest-agent | Installed and enabled |
| Optional Tailscale join | Yes — when `tailscale_auth_key` is set (GitHub secret `TAILSCALE_VM_AUTHKEY` or tfvars) |
| Resource tags | Yes — per-machine `tags` in `machines` map |
| Unprivileged LXC default | Yes — `proxmox-compute` default for LXC type |

**Not enforced by OpenTofu/cloud-init today:**

- Disable root SSH login
- Separate `gitops` deploy user
- Firewall (ufw/nftables)
- Fail2Ban
- Security update policy
- Lynis audit
- Tailscale SSH for humans (only `tailscale up` install/join is wired)

Packer-built Debian templates also bake SSH keys into the template and lock the
temporary `packer` user before templating — see `infra/packer/templates/debian-13/`.

## Target baseline (phase 2C — Ansible, not implemented)

Ansible roles in `builders/ansible/roles/` are **debug placeholders** today.
Each role prints `TODO:` and does not change the host. The `harden.yml` playbook
exists but is not production-ready.

When implemented, phase 2C should add:

| Control | Role |
|---------|------|
| Package refresh + update policy | `base-linux` |
| Human admin user hardening | `base-linux` / `ssh-hardening` |
| `gitops` deploy user + restricted sudo | `gitops-user` |
| Disable root SSH | `ssh-hardening` |
| Disable password SSH | `ssh-hardening` |
| Default-deny firewall | `firewall` |
| Tailscale + private management access | `tailscale` |
| Optional Docker runtime | `docker-host` |
| Fail2Ban, Lynis | future roles or extensions |

Same roles should work for Proxmox VMs/LXCs (`inventories/lab/`) and future VPS
hosts (`inventories/vps/`).

## What you can verify today

After Packer + local OpenTofu apply with a `builder_target` VM:

```bash
ssh autolab@<vm-ip-or-tailscale-name>    # should work with your laptop key
```

Optional if `tailscale_auth_key` was set:

```bash
tailscale status                         # VM should appear on tailnet
```

## Acceptance checks (phase 2C target)

These checks apply **after Ansible hardening is implemented**, not today:

```bash
ssh root@HOSTNAME                        # should fail
ssh -o PreferredAuthentications=password USER@HOSTNAME   # should fail
tailscale ssh ADMIN_USER@HOSTNAME        # should work
sudo ufw status verbose                  # should show active policy
ss -tulpn                                # only expected ports
```

## Public exposure rule

Public internet exposure is opt-in only.

Default management access:

1. Tailscale for reachability (VM join via cloud-init when auth key is set).
2. SSH with injected public keys to the admin user.
3. Proxmox UI over Tailscale/private network.

Do not forward port 22 from the public internet to lab machines by default.

## Related docs

- [GitOps README](./README.md) — phase map (2A vs 2C)
- [OpenTofu VM/LXC provisioning](./04-opentofu-vm-lxc.md) — `machines` and cloud-init
- [builders/ansible/README.md](../../builders/ansible/README.md) — builder scaffold
