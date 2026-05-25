# Proxmox VE — post-install network runbook (USB Ethernet + Wi‑Fi + routing)

Step-by-step record for a **Dell XPS 15 9560** with **USB‑C Ethernet (Anker hub, ASIX `enx…`)**, **Intel Wi‑Fi `wlp2s0`**, static **`vmbr0`**, home SSID **`kasar_5`**, and a phone hotspot as lower priority. Substitute your own interface names, IPs, subnets, and passwords everywhere marked.

**Convention:** `ETH_USB` = USB Ethernet interface (example: `enxf8e43b3a8d38`). `WIFI` = Wi‑Fi (example: `wlp2s0`). `GW` = LAN default gateway (example: `192.168.50.1`). `VMBR_IP` = static address on `vmbr0` (example: `192.168.50.130/24`).

---

## 1. Discover interface names

```bash
ip link show
ip -br a
```

Confirm:

- Which interface is **USB Ethernet** (often `enx` + MAC-derived suffix).
- Which is **Wi‑Fi** (often `wlp…`).

If the installer created **`vmbr0`** with the wrong `bridge-ports` (e.g. `nic0` instead of the USB NIC), fix that in **section 2** before relying on the web UI.

---

## 2. Fix `vmbr0` bridge port (USB Ethernet, not wrong NIC)

Edit:

```bash
nano /etc/network/interfaces
```

`vmbr0` must use **`bridge-ports ETH_USB`** (your real `enx…` name). The physical USB NIC stanza should be `iface ETH_USB inet manual`. Example shape:

```text
iface ETH_USB inet manual

auto vmbr0
iface vmbr0 inet static
        address VMBR_IP
        gateway GW
        bridge-ports ETH_USB
        bridge-stp off
        bridge-fd 0
```

Apply:

```bash
systemctl restart networking
```

Verify:

```bash
ip a show vmbr0
ip a show ETH_USB
```

---

## 3. APT on a new node

Configure package sources and run `apt update` **before** the `apt install` steps below. Use **[04-apt-updates-tailscale.md](./04-apt-updates-tailscale.md)** (repository setup and first refresh).

---

## 4. Install Wi‑Fi client packages

```bash
apt install -y wpasupplicant wireless-tools
```

---

## 5. `wpa_supplicant` — multiple SSIDs and priority

Create or edit:

```bash
nano /etc/wpa_supplicant/wpa_supplicant.conf
```

Template (replace `country`, SSIDs, and PSKs). **Higher `priority` = preferred among Wi‑Fi networks** when several are configured and visible.

```text
ctrl_interface=/run/wpa_supplicant
update_config=1
country=US

network={
    ssid="HOME_SSID"
    psk="HOME_WPA_PSK"
    priority=10
}

network={
    ssid="HOTSPOT_SSID"
    psk="HOTSPOT_WPA_PSK"
    priority=5
}
```

**SSID characters:** avoid apostrophes and “smart quotes” in hotspot names. If `scan_results` shows `\xe2\x80\x99` in the SSID, the AP is using a Unicode apostrophe; either use a hex SSID in `wpa_supplicant` or **rename the hotspot** to plain ASCII (this install used a renamed hotspot, e.g. `MahirsIphone`, to avoid encoding issues).

Manual bring-up test (before persisting in `/etc/network/interfaces`):

```bash
wpa_supplicant -B -i WIFI -c /etc/wpa_supplicant/wpa_supplicant.conf
dhclient WIFI
ip a show WIFI
```

Stop manual test if you need a clean slate:

```bash
killall wpa_supplicant
dhclient -r WIFI 2>/dev/null || true
```

---

## 6. Kernel: IP forwarding and ignore link-down default routes

```bash
grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.conf || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
grep -q 'ignore_routes_with_linkdown' /etc/sysctl.conf || echo 'net.ipv4.conf.all.ignore_routes_with_linkdown=1' >> /etc/sysctl.conf
sysctl -p
```

`ignore_routes_with_linkdown=1` avoids the kernel preferring a **dead** default route on `vmbr0` when the USB Ethernet is unplugged but the route still exists with a better metric.

---

## 7. NAT from guest/VM network out via Wi‑Fi (optional)

This transcript used **MASQUERADE** for a specific source range. **Replace `GUEST_NET` with the CIDR that actually matches your design** (NAT internal subnet for guests, or omit this section if you do not SNAT VM traffic out `WIFI`).

```bash
iptables -t nat -A POSTROUTING -s GUEST_NET -o WIFI -j MASQUERADE
apt install -y iptables-persistent
netfilter-persistent save
```

Example only (verify before use): `GUEST_NET=10.0.0.0/24`.

---

## 8. `/etc/network/interfaces` — final combined layout

This is the **working shape** from the same install: DHCP on Wi‑Fi + static `vmbr0` on USB Ethernet, **metric 100** on `vmbr0` default route, **metric 200** backup default on Wi‑Fi, and `post-up` lines to deduplicate DHCP’s default route on Wi‑Fi.

Replace `ETH_USB`, `WIFI`, `VMBR_IP`, `GW`.

```text
auto lo
iface lo inet loopback

auto WIFI
iface WIFI inet dhcp
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf
    post-up ip route add default via GW dev WIFI metric 200 || true
    post-up ip route del default via GW dev WIFI 2>/dev/null || true

iface ETH_USB inet manual

auto vmbr0
iface vmbr0 inet static
        address VMBR_IP
        gateway GW
        metric 100
        bridge-ports ETH_USB
        bridge-stp off
        bridge-fd 0

source /etc/network/interfaces.d/*
```

Apply:

```bash
systemctl restart networking
```

Verify routing:

```bash
ip route
```

Expected pattern when Ethernet is **up**: default via `vmbr0` **metric 100**, and default via `WIFI` **metric 200**. When Ethernet is **down** and `ignore_routes_with_linkdown` is set, traffic should use the Wi‑Fi default.

---

## 9. Router list vs what you type in the browser (DHCP in plain terms)

**DHCP** means: when a network card **asks** the router for an address, the router **answers** with one from its pool (or with a fixed address if you configured one for that card).

Your Proxmox box can have **more than one** address at the same time because it has **more than one** path to the LAN (for example USB Ethernet on `vmbr0` **and** Wi‑Fi).

| Where the address is set | Who decides the number | Typical result |
|--------------------------|-------------------------|----------------|
| **`vmbr0` in `/etc/network/interfaces`** (static) | **You** on the Proxmox host | The host **always** uses that IP on the bridge (e.g. `192.168.50.130`) **without** the router “giving” it that lease. You open the web UI at `https://192.168.50.130:8006` because Proxmox configured it there. |
| **Wi‑Fi with `iface … inet dhcp`** | **The router** (DHCP) | The router’s **client list** or **DHCP lease** view shows whatever address DHCP last gave **that Wi‑Fi chip** (e.g. `.124`). That line is about **Wi‑Fi**, not about the static `vmbr0` address. |

So it is normal to see **one IP in the router UI** (often the Wi‑Fi lease, e.g. `.124`) while you still **reach Proxmox at `.130`**: you are usually hitting **`vmbr0`’s static address** on USB Ethernet, which never depended on that Wi‑Fi line in the router.

**“Manual assignment” / “DHCP reservation”** on the router is only: *when this **MAC address** (one specific network card) asks for DHCP, answer with **this** IP.* It does not replace or override the static IP you typed into Proxmox for `vmbr0`; it only affects **that MAC’s** DHCP replies.

Practical checklist:

1. Decide which address you use in the browser for the UI (**often `vmbr0`’s static IP** when the USB path is up).
2. If you also want **Wi‑Fi** to get a **predictable** address from the router, add a reservation row for the **Wi‑Fi MAC** and the IP you want **for Wi‑Fi** — and **Apply**. Until Wi‑Fi renews its lease, the router screen can still show an older address (e.g. `.124`); **reboot** or renew DHCP on Wi‑Fi updates that display.
3. Do not give **two different cards on the same machine** the **same** IPv4 on the same subnet **at the same time** with both links up; pick different numbers or only use one path.

---

## 10. Two separate “priority” concepts

| Layer | Mechanism | Meaning |
|-------|-----------|---------|
| **Ethernet vs Wi‑Fi** | `ip` route **metrics** on default routes | **Lower metric = preferred.** `vmbr0` at 100, `WIFI` at 200 in this setup. |
| **Among Wi‑Fi SSIDs** | `wpa_supplicant` **`priority` inside each `network{}`** | **Higher number = preferred** when multiple configured networks are available. |

---

## 11. USB Ethernet replug — `vmbr0` loses bridge port (Thunderbolt / hub reset)

Unplugging the hub removed the NIC from the bridge; `vmbr0` stayed up administratively but had **no slave port**. A small **systemd** service polls and re-attaches the NIC to `vmbr0`.

**`/usr/local/bin/vmbr0-watch.sh`** (replace `ETH_USB`):

```bash
cat > /usr/local/bin/vmbr0-watch.sh << 'EOF'
#!/bin/bash
ETH_USB="enxf8e43b3a8d38"
while true; do
    if ip link show "$ETH_USB" &>/dev/null; then
        if ! bridge link show | grep -q "$ETH_USB"; then
            echo "$(date): Re-enslaving ${ETH_USB} to vmbr0..."
            ip link set "$ETH_USB" up
            sleep 1
            ip link set "$ETH_USB" master vmbr0
            ip link set vmbr0 up
            echo "$(date): Done."
        fi
    fi
    sleep 3
done
EOF
chmod +x /usr/local/bin/vmbr0-watch.sh
```

**`/etc/systemd/system/vmbr0-watch.service`:**

```bash
cat > /etc/systemd/system/vmbr0-watch.service << 'EOF'
[Unit]
Description=Re-attach USB Ethernet to vmbr0 when replugged

[Service]
Type=simple
ExecStart=/usr/local/bin/vmbr0-watch.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable --now vmbr0-watch
```

Live log:

```bash
journalctl -u vmbr0-watch -f
```

---

## 12. Operational checks

```bash
ip route
ip a show vmbr0
ip a show WIFI
ping -c 3 GW
ping -c 3 8.8.8.8
bridge link show
```

**Web UI:** when only Wi‑Fi has carrier, browse to `https://<WIFI_DHCP_IP>:8006` if `vmbr0` has no path; when USB Ethernet is up, `https://<VMBR_STATIC_IP>:8006` is typical.

---

## 13. `wpa_cli` — inspect, force rescan, toggle networks

```bash
wpa_cli -i WIFI status
wpa_cli -i WIFI list_networks
```

Reload config after editing `wpa_supplicant.conf`:

```bash
wpa_cli -i WIFI reconfigure
wpa_cli -i WIFI list_networks
```

Force disconnect / reconnect:

```bash
wpa_cli -i WIFI disconnect
wpa_cli -i WIFI reconnect
```

Temporarily disable a network by **id** from `list_networks` (e.g. `0` = first SSID):

```bash
wpa_cli -i WIFI disable_network 0
wpa_cli -i WIFI reconnect
```

Re-enable:

```bash
wpa_cli -i WIFI enable_network 0
wpa_cli -i WIFI reconnect
```

Scan and grep SSID:

```bash
wpa_cli -i WIFI scan
sleep 3
wpa_cli -i WIFI scan_results
```

---

## 14. After editing `wpa_supplicant.conf` or `interfaces`

Prefer:

```bash
wpa_cli -i WIFI reconfigure
systemctl restart networking
```

If behaviour is unclear, a **reboot** is the definitive test for ordering and persistence.

---

## 15. Related docs in this repo

- [01-bare-metal-dell-xps.md](./01-bare-metal-dell-xps.md) — install and BIOS.
- [02-host-networking-wifi.md](./02-host-networking-wifi.md) — shorter design notes and SSID pitfalls.
- [04-apt-updates-tailscale.md](./04-apt-updates-tailscale.md) — repos, upgrades, Tailscale.

---

## 16. Checklist (copy for your next node)

- [ ] [04-apt-updates-tailscale.md](./04-apt-updates-tailscale.md) — repositories, `apt update`, upgrade path, Tailscale on the node.
- [ ] `ip link` — record `ETH_USB`, `WIFI`.
- [ ] `/etc/network/interfaces` — `vmbr0` → `ETH_USB`; static `VMBR_IP`; `WIFI` + `wpa-conf` + `post-up` routes.
- [ ] `/etc/wpa_supplicant/wpa_supplicant.conf` — `country`, `network{}` blocks, priorities, ASCII SSIDs.
- [ ] `/etc/sysctl.conf` — `ip_forward`, `ignore_routes_with_linkdown`.
- [ ] `iptables` NAT — only if needed; **correct `GUEST_NET` and `-o WIFI`**.
- [ ] `iptables-persistent` / `netfilter-persistent save`.
- [ ] `vmbr0-watch.sh` + `vmbr0-watch.service` — **set `ETH_USB` in script**; `daemon-reload`, `enable --now`.
- [ ] Router: optional **DHCP reservation** for the **Wi‑Fi MAC** if you want a stable Wi‑Fi lease; **Apply**; renew or reboot so the list matches reality. **Browser URL** for the UI usually follows **`vmbr0`’s static IP** from Proxmox, not necessarily the same line as the router’s Wi‑Fi lease.
- [ ] Reboot test; confirm `ip route` and `wpa_cli status` after cold boot.
