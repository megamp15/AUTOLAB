# Proxmox (xps-pve)

Read in order for a first-time bring-up.

| Order | File | Contents |
|-------|------|----------|
| 01 | [01-bare-metal-dell-xps.md](./01-bare-metal-dell-xps.md) | ISO install, BIOS |
| 02 | [02-host-networking-wifi.md](./02-host-networking-wifi.md) | Wi‑Fi on the hypervisor (overview) |
| 03 | [03-post-install-network-runbook.md](./03-post-install-network-runbook.md) | USB `vmbr0`, Wi‑Fi, routing, DHCP notes, `vmbr0-watch` |
| 04 | [04-apt-updates-tailscale.md](./04-apt-updates-tailscale.md) | `apt` / repos, upgrades, Tailscale on the node |

Later automation (Terraform, GitHub Actions, Ansible) assumes **04** is done so the host has a reachable API path (often via Tailscale).
