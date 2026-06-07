# Autolab documentation

Autolab docs are organized by **platform** and **maturity**. Each guide uses optional frontmatter (`tags`, `status`, `audience`) so the set can grow without losing structure.

## Doc tags (convention)

| Field | Meaning | Examples |
|-------|---------|----------|
| `tags` | Search / filter topics | `proxmox`, `networking`, `beginner` |
| `status` | How complete the guide is | `alpha` (project), `draft`, `stable` (when a guide is frozen) |
| `audience` | Who it’s for | `beginner`, `operator` |

## Proxmox hypervisor

**[proxmox/README.md](./proxmox/README.md)** — index for the single-node path.

| Order | Guide | File |
|-------|--------|------|
| 1 | Install OS | [01-bare-metal-install.md](./proxmox/01-bare-metal-install.md) |
| 2 | SSH + network scripts | [00-fresh-install-network.md](./proxmox/00-fresh-install-network.md) |
| 3 | APT maintenance (ongoing) | [04-apt-maintenance.md](./proxmox/04-apt-maintenance.md) |
| 4 | Tailscale (optional) | [05-tailscale.md](./proxmox/05-tailscale.md) |
| — | Major PVE upgrade (rare) | [06-proxmox-version-upgrade.md](./proxmox/06-proxmox-version-upgrade.md) |

**Why is step 2 named `00-`?** Filenames sort network setup before maintenance (`04+`) while install stays `01-`.

**Reference (not step-by-step):** [02 Wi‑Fi concepts](./proxmox/02-host-networking-wifi.md) · [03 Troubleshooting](./proxmox/03-post-install-network-runbook.md)

**Scripts:** [proxmox/scripts/README.md](./proxmox/scripts/README.md)

**Per-machine config template:** [proxmox/config/network.env.example](./proxmox/config/network.env.example) → on the host becomes `/etc/default/proxmox-network.env`

## Roadmap

Planned work (IaC, CI, more nodes): [ROADMAP.md](./ROADMAP.md)

## GitOps

**[gitops/README.md](./gitops/README.md)** - phase 2 track for secure VM/LXC creation with OpenTofu, GitHub Actions, and Tailscale.
