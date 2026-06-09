# Autolab

**[Features](#features) • [Get started](#get-started) • [Documentation](docs/README.md) • [Roadmap](docs/ROADMAP.md)**

[![project status](https://img.shields.io/badge/status-alpha-orange?style=flat-square)](docs/ROADMAP.md)
[![docs](https://img.shields.io/badge/docs-proxmox%20guides-0E8A16?style=flat-square&logo=gitbook&logoColor=white)](docs/proxmox/README.md)
[![proxmox](https://img.shields.io/badge/hypervisor-Proxmox%20VE-E57000?style=flat-square&logo=proxmox&logoColor=white)](https://www.proxmox.com/)
[![hosts](https://img.shields.io/badge/hosts-per%20machine-1f6feb?style=flat-square)](docs/proxmox/README.md)
[![scripts CI](https://img.shields.io/github/actions/workflow/status/megamp15/AUTOLAB/scripts.yml?style=flat-square&logo=github&label=scripts)](https://github.com/megamp15/AUTOLAB/actions/workflows/scripts.yml)
[![license](https://img.shields.io/github/license/megamp15/AUTOLAB?style=flat-square)](LICENSE)
[![stars](https://img.shields.io/github/stars/megamp15/AUTOLAB?logo=github&logoColor=white&color=gold&style=flat-square)](https://github.com/megamp15/AUTOLAB)

Autolab is a **custom, learning-first homelab** you build yourself: versioned docs and bash automation for a **Proxmox** hypervisor—run the same flow again on a **second box** with that machine’s own config file, with secrets kept on each host—not in git. The path leads to **infrastructure as code** and **GitHub Actions**, without pretending to be a one-size-fits-all product.

> **How is this different from a full “homelab in a box” repo?**  
> Projects like [khuedoan/homelab](https://github.com/khuedoan/homelab) target multi-node Kubernetes, GitOps, and a large app stack. **Autolab** starts smaller: one Proxmox hypervisor, reproducible networking (USB Ethernet + Wi‑Fi failover), and tutorials you can fork for your own hardware. Same *idea* (IaC + learn by doing); different **scope** (Proxmox-first, fully yours to extend).

> **Disclaimer** — Scripts change network config and may drop SSH briefly. Use at your own risk; keep local console or a second access path (e.g. Tailscale). Backups are written under `/root/proxmox-network-backup-*` before apply.

## Overview

| | |
|--|--|
| **Status** | **Alpha** — network path is usable; IaC/CI expanding ([roadmap](docs/ROADMAP.md)) |
| **Hardware** | Repurposed laptop-class PC (e.g. Dell XPS) + USB Ethernet; Wi‑Fi for backup |
| **Goal** | Portable lab: predictable management IP, failover, demos, then automate everything |

## Features

- [x] Proxmox bare-metal install guide
- [x] Interactive network wizard (`/etc/default/proxmox-network.env`)
- [x] One-shot apply: `interfaces`, `wpa_supplicant`, failover + `vmbr0-watch`
- [x] USB Ethernet later (`enable-usb-ethernet.sh`) without redoing Wi‑Fi from scratch
- [x] Extra Wi‑Fi networks (home, phone hotspot, more SSIDs)
- [x] Host-only secrets; repo stays generic
- [x] Troubleshooting runbook (incl. Wi‑Fi password / terminal pitfalls)
- [x] GitOps phase 2A docs + OpenTofu VM/LXC scaffold
- [x] GitHub Actions CI, plan, and apply workflows (ephemeral Tailscale runner)
- [x] Cloudflare R2 state backend + Packer template scaffold
- [x] Packer VM template build workflow
- [x] Schema-driven code generation (connection schema → OpenTofu/Packer adapters, network env schema → env file + validation)
- [x] Production-readiness checks for retry behaviour, R2 setup output, cloud-init Tailscale enrollment, and generated adapter validation
- [ ] Ansible hardening roles (one role per server baseline)
- [ ] Service/VM tutorials on top of PVE

## Get started

1. **[docs/proxmox/README.md](docs/proxmox/README.md)** — index and glossary  
2. **[01 Install Proxmox](docs/proxmox/01-bare-metal-install.md)**  
3. **[00 Network over SSH](docs/proxmox/00-fresh-install-network.md)** — copy scripts, wizard, apply  

```bash
# On your laptop
scp -r ./docs/proxmox/* root@PROXMOX_IP:/root/proxmox-setup/

# On the Proxmox host (root)
cd /root/proxmox-setup/scripts
bash configure-proxmox-network-env.sh
bash setup-proxmox-network.sh --apply
```

## Design principles

- **Learn homelabbing** — read why, not only copy-paste  
- **Custom stack** — you choose SSIDs, IPs, and what to add next  
- **Bootstrap first** — host must get online manually (install + network scripts); **GitOps comes after** the node can reach git/your automation  
- **Repeat per machine** — each host gets its own `/etc/default/proxmox-network.env`  
- **Portable** — move the box, re-run setup or `enable-usb-ethernet.sh` as needed  

## Repository map

| Path | Purpose |
|------|---------|
| [docs/proxmox/](docs/proxmox/) | Guides + scripts (current focus) |
| [docs/gitops/](docs/gitops/) | Phase 2A GitOps docs for secure VM/LXC creation |
| [infra/](infra/) | Terramate + OpenTofu stacks and modules |
| [infra/stacks/](infra/stacks/) | Environment stacks (lab, prod, etc.) |
| [infra/modules/](infra/modules/) | Shared Proxmox compute and connection modules |
| [infra/_base/](infra/_base/) | Terramate code generation (providers, backend) |
| [infra/packer/](infra/packer/) | Packer VM template builds (phase 2B scaffold) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Now / next / non-goals |
| [docs/production-readiness.md](docs/production-readiness.md) | Stop criteria for using Autolab (schema drift, tests, smoke test) |
| [docs/proxmox/config/network.env.example](docs/proxmox/config/network.env.example) | Template → `/etc/default/proxmox-network.env` on host |

## GitHub topics

Set on the repo for discoverability:

`homelab` `proxmox` `networking` `wifi` `infrastructure-as-code` `learning` `documentation` `bash` `self-hosted` `portable`

## License

[MIT](LICENSE) — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.
