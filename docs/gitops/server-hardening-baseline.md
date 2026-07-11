---
tags: [gitops, security, hardening, ssh, tailscale]
status: draft
audience: operator
---

# Server hardening baseline

Every Autolab VM, supported LXC, or VPS should be treated like a small server on an untrusted network. Proxmox and VPS providers differ at provisioning time; after SSH is reachable, the hardening baseline should be shared.

## Phase 2A baseline

OpenTofu should make unsafe defaults harder:

- inject SSH public keys only
- avoid password login
- avoid public management ports
- create or prepare a non-root admin user where the template supports it
- tag resources as `autolab` and by profile
- prefer Tailscale/private management access
- use unprivileged LXCs by default

## Phase 2C builder baseline

Ansible builder roles will enforce the full OS hardening baseline:

- create the human admin user
- create the separate `gitops` deploy user
- disable root SSH login
- disable password SSH login
- restrict sudo intentionally
- configure firewall defaults
- allow SSH only from Tailscale/private management networks
- install and enable Tailscale
- enable Tailscale SSH for human access
- install security updates or document the update policy
- enable Fail2Ban where SSH is reachable
- run a simple Lynis audit

The same roles should be usable from a `lab` inventory for Proxmox-created hosts and a future `vps` inventory for cloud-provider hosts. Project-specific roles can build on this baseline, but should not weaken it by default.

## Acceptance checks

These should eventually become automated checks:

```bash
ssh root@HOSTNAME
ssh -o PreferredAuthentications=password USER@HOSTNAME
tailscale ssh ADMIN_USER@HOSTNAME
sudo ufw status verbose
ss -tulpn
```

Expected result:

- root SSH fails
- password SSH fails
- non-root Tailscale SSH works
- firewall is active
- only expected ports listen

## Public exposure rule

Public internet exposure is opt-in only.

Default management access is:

1. Tailscale SSH for humans.
2. OpenSSH over Tailscale/private network for automation.
3. Proxmox UI over Tailscale/private network.

Do not forward port 22 from the public internet to lab machines by default.
