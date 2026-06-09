---
tags: [gitops, security, references]
status: draft
audience: maintainer
---

# Security sources

Autolab should not use a single blog post as its source of truth. These are the references behind the hardening baseline.

## Primary references

| Area | Source | Why |
|------|--------|-----|
| General server security | [NIST SP 800-123](https://csrc.nist.gov/pubs/sp/800/123/final) | Baseline for server lifecycle, patching, least privilege, logs, backups, and incident response |
| Linux benchmark | [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks) | Enterprise hardening baseline |
| Ubuntu hardening | [Ubuntu security docs](https://ubuntu.com/server/docs/security-introduction) | Distro-native hardening guidance |
| Debian hardening | [Securing Debian Manual](https://www.debian.org/doc/manuals/securing-debian-manual/index.en.html) | Debian-specific hardening reference |
| SSH hardening | [Mozilla OpenSSH guidelines](https://mozilla.github.io/infosec.mozilla.org/guidelines/openssh) | Practical SSH configuration guidance |
| SSH implementation | [OpenSSH manuals](https://www.openssh.com/manual.html) | Source for exact SSH options |
| Tailscale SSH | [Tailscale SSH docs](https://tailscale.com/docs/features/tailscale-ssh) | Tailnet identity and SSH access model |
| Tailnet policy | [Tailscale ACL syntax](https://tailscale.com/kb/1337/acl-syntax/) | Source for Tailscale access controls |
| Proxmox security | [Proxmox VE admin guide](https://pve.proxmox.com/pve-docs/pve-admin-guide.html) | Users, permissions, API tokens, firewall |
| LXC security | [Proxmox Linux containers](https://pve.proxmox.com/wiki/Linux_Container) | Unprivileged container guidance and tradeoffs |
| Linux audit | [Lynis](https://cisofy.com/lynis/) | Lightweight local audit tool |
| Continuous assessment | [Wazuh SCA](https://documentation.wazuh.com/current/user-manual/capabilities/sec-config-assessment/index.html) | Later CIS-style continuous assessment |

## Supplemental beginner references

| Source | Use |
|--------|-----|
| [Hostinger VPS security guide](https://www.hostinger.com/tutorials/vps-security) | Beginner-friendly overview of common VPS controls |
| [DigitalOcean initial server setup](https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu) | Simple explanation of users, SSH, and firewall |

## Autolab default stance

- Follow the practical baseline first.
- Treat CIS Level 1 as the later enterprise learning target.
- Avoid CIS Level 2 or STIG-style strictness until there is a dedicated advanced guide.
- Prefer VMs over LXCs for public-facing or high-risk workloads.
- Prefer unprivileged LXCs for lightweight internal services.
