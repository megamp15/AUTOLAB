---
tags: [proxmox, bash, networking, scripts]
status: alpha
audience: beginner
---

# Scripts — run on the Proxmox host as root

Files in git under `docs/proxmox/scripts/`. They do **nothing** until you copy `docs/proxmox/*` to `/root/proxmox-setup/` on the host and run them as **root**.

## Where they go

```mermaid
flowchart LR
  A[Autolab repo\non laptop or USB] -->|copy| B["/root/proxmox-setup/"]
  B --> C[setup-proxmox-network.sh]
  C --> D["/usr/local/bin/"]
  C --> E["/etc/"]
  C --> F[systemd]
```

| On Proxmox | Path |
|------------|------|
| Copied folder | `/root/proxmox-setup/scripts/*.sh` (+ `scripts/lib/`) |
| Installed by setup | `/usr/local/bin/network-uplink-failover.sh` |
| Installed by setup | `/usr/local/bin/vmbr0-watch.sh` (static file, reads config at runtime) |

## Main scripts (new machine)

Use `--dry-run` with either script to preview changes without modifying the system:

```bash
cd /root/proxmox-setup/scripts
bash configure-proxmox-network-env.sh --dry-run           # preview env file without writing
bash setup-proxmox-network.sh --dry-run                   # preview all configs without writing
bash configure-proxmox-network-env.sh                     # Wi-Fi (+ hotspot + more networks); writes /etc/default/proxmox-network.env
bash setup-proxmox-network.sh --apply                     # applies Wi-Fi, vmbr0, failover
```

| Task | Script |
|------|--------|
| Home Wi‑Fi + phone hotspot + more SSIDs | `configure-proxmox-network-env.sh` |
| Preview env file without writing | `configure-proxmox-network-env.sh --dry-run` |
| Preview all configs without applying | `setup-proxmox-network.sh --dry-run` |
| USB Ethernet **after** first run (ETH_USB was empty) | [enable-usb-ethernet.sh](./enable-usb-ethernet.sh) |
| Re-apply after editing env | `setup-proxmox-network.sh --apply --skip-apt` |

Config files on the host:

| Path | Contents |
|------|----------|
| `/etc/default/proxmox-network.env` | Main settings (SSID, PSK, GW, `ETH_USB`, `VMBR_IP`) |
| `/etc/default/proxmox-wifi-extra.list` | Intentional sidecar for optional extra SSIDs (`SSID\|PSK\|priority` per line) |

Shared libraries:

| File | Role |
|------|------|
| [lib/detect.sh](./lib/detect.sh) | Interface detection and suggestion (`detect_iface`, `detect_gw`, `suggest_vmbr_ip`) |
| [lib/env-config.sh](./lib/env-config.sh) | Env file format, reading and writing (`write_env`, `env_file_set`, `write_failover_env`, `prompt_into`) |
| [lib/network-render.sh](./lib/network-render.sh) | Pure config rendering (`render_interfaces`, `render_wpa_header`, `append_wpa_network`) |
| [lib/network-env-schema.sh](./lib/network-env-schema.sh) | Generated Network env schema keys, defaults, and validation helpers |
| [lib/network-env-schema.sh](./lib/network-env-schema.sh) | Auto-generated from [`network-env-schema.yaml`](../config/network-env-schema.yaml) — validates env file against schema and provides schema-key iteration/default application helpers for bootstrap scripts |
| [lib/proxmox-env.sh](./lib/proxmox-env.sh) | Compatibility shim — sources `env-config.sh` + `network-render.sh` |

## Other scripts

| Script | When |
|--------|------|
| [setup-proxmox-network.sh](./setup-proxmox-network.sh) | **New node** — full install |
| [enable-usb-ethernet.sh](./enable-usb-ethernet.sh) | Plug in USB NIC; set `ETH_USB` and apply |
| [refresh-network-scripts-from-repo.sh](./refresh-network-scripts-from-repo.sh) | Refresh `/usr/local/bin` from repo copy on host |
| [sync-host-to-docs.sh](./sync-host-to-docs.sh) | Deprecated alias → `refresh-network-scripts-from-repo.sh` |
| [install-network-uplink-failover.sh](./install-network-uplink-failover.sh) | Repair failover only (needs env vars) |
| [install-vmbr0-watch.sh](./install-vmbr0-watch.sh) | Install vmbr0-watch (copies static script + systemd unit) |
| [vmbr0-watch.sh](./vmbr0-watch.sh) | Static watch script — reads config from `/etc/default/network-uplink-failover` at runtime |
| [network-uplink-failover.sh](./network-uplink-failover.sh) | Ethernet/Wi-Fi failover daemon |

Guide: [../00-fresh-install-network.md](../00-fresh-install-network.md)
