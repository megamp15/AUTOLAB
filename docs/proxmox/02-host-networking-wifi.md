# Proxmox VE — Wi-Fi on the hypervisor

Proxmox is based on Debian. A wired Ethernet uplink is the default recommendation for the management network and for bridges such as `vmbr0`. **Wi-Fi** can be used for **host management only** (SSH, web UI, package updates) with additional configuration.

For a full command-and-file runbook (USB Ethernet bridge fix, `wpa_supplicant`, routing metrics, sysctl, iptables NAT, `vmbr0-watch`, `wpa_cli`), see [03-post-install-network-runbook.md](./03-post-install-network-runbook.md).

For `apt` repositories, upgrades, and **Tailscale on the node**, see [04-apt-updates-tailscale.md](./04-apt-updates-tailscale.md).

## Design notes

- **Bridging**: VM bridges are most straightforward with a physical Ethernet interface. Wi-Fi uplinks complicate bridging; see Proxmox documentation for routed/NAT approaches if VMs require outbound Internet.
- **Management over Wi-Fi**: Supported in principle via Debian networking (`/etc/network/interfaces`, `wpa_supplicant`). A USB Ethernet adapter reduces configuration time for the management path.

## Wi-Fi configuration

1. Identify the Wi-Fi interface (e.g. `wlp…`) with `ip link`.
2. Use **DHCP** on networks that provide it (typical home routers).
3. When changing uplinks (e.g. home WLAN to phone hotspot), update SSID/credentials in `wpa_supplicant` (or equivalent), restart the interface or networking service, or reboot.

Common configuration paths:

- **`/etc/network/interfaces`** with `allow-hotplug` and `wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf`
- Manual bring-up with **`wpa_supplicant`** and **`dhclient`** for testing, then persist the working configuration

Set `country=XX` in `wpa_supplicant` to the correct regulatory domain; incorrect or missing country settings can limit 5 GHz channel availability. Official examples are in the Proxmox wiki and forum.

## SSID special characters (e.g. apostrophe)

Hotspot SSIDs may include characters such as **`'`** (apostrophe). Those characters can break shell snippets or mis-nest quotes in `wpa_supplicant` stanzas unless escaped correctly.

**Mitigation**: use an SSID limited to alphanumeric characters and hyphens, and avoid spaces where possible.

**Alternative**: use the escaping rules for the configuration file in use, or an SSID encoded in hex in `wpa_supplicant.conf` per `wpa_supplicant` documentation.

## Connectivity checks

```bash
ip link
iw dev <iface> scan | less
ping -c 3 1.1.1.1
curl -I https://www.proxmox.com
```

Replace `<iface>` with the Wi-Fi interface name.

If the host obtains DHCP on Wi-Fi but **guests have no Internet**, verify bridge/NAT design and that `vmbr0` (or the chosen bridge) is tied to the correct physical interface per Proxmox networking documentation.

## Remote API access

Automation (e.g. Terraform, CI pipelines) requires a stable hostname or IP that reaches the Proxmox API (HTTPS port 8006). Install **Tailscale on the Proxmox host** per [04-apt-updates-tailscale.md](./04-apt-updates-tailscale.md).
