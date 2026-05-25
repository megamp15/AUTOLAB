# Proxmox VE — `apt`, upgrades, and Tailscale on the node

Run on the **Proxmox host as root** (SSH or local console). Order matters: fix **APT sources** first, then **refresh the index**, then **upgrade**, then add **Tailscale** for remote API/SSH access.

---

## 1. What the commands do

| Command | Purpose |
|---------|---------|
| **`apt update`** | Downloads fresh package **indexes** from all configured repositories. Does not upgrade installed packages. Run this **before** `apt install` or upgrades whenever sources change or daily during maintenance. |
| **`apt upgrade`** / **`apt full-upgrade`** / **`apt dist-upgrade`** | Installs newer package versions. Proxmox documents which form to use for **major/minor** upgrades; follow the official **Upgrade** article for your PVE major version so kernel and userland stay consistent. |

---

## 2. Why `apt update` fails on a fresh non-subscription node

Default installs enable **enterprise** repository entries that require a **subscription**. Without one, `apt update` reports **401** (or similar) for those URLs.

**Fix:** disable the enterprise lists (or comment them out), then add the **no-subscription** Proxmox repository that matches your **Debian base** (codename).

---

## 3. Read your Debian codename (required once)

```bash
grep VERSION_CODENAME /etc/os-release
```

Example output: `VERSION_CODENAME=trixie` or `bookworm`. The **no-subscription** `deb` line must use **that** codename.

---

## 4. One-time repository setup (no subscription)

Disable the enterprise feeds (idempotent if already disabled):

```bash
echo "# pve-no-subscription setup — enterprise disabled" > /etc/apt/sources.list.d/pve-enterprise.list
echo "# disabled" > /etc/apt/sources.list.d/ceph.list
```

Add **no-subscription** using the codename from the host:

```bash
. /etc/os-release
echo "deb http://download.proxmox.com/debian/pve ${VERSION_CODENAME} pve-no-subscription" > /etc/apt/sources.list.d/pve-no-subscription.list
```

Refresh the index:

```bash
apt update
```

`apt update` should complete **without 401** errors for Proxmox URLs. If errors remain, inspect:

```bash
ls -la /etc/apt/sources.list.d/
cat /etc/apt/sources.list
```

---

## 5. `Temporary failure resolving` (GUI Repositories / `apt update`)

Example: `Failed to fetch http://ftp.debian.org/... Temporary failure resolving 'ftp.debian.org'`.

That means **DNS resolution failed** (the hostname did not resolve to an IP). Common causes: **no working default route** to the internet, or **resolvers in `/etc/resolv.conf`** not reachable.

| Check | Command | If it fails |
|-------|---------|-------------|
| Outbound path | `ip route get 8.8.8.8` | Default route or interface selection is wrong |
| LAN gateway | `ping -c 2 192.168.50.1` | Replace with your gateway; confirms local routing |
| Internet without DNS | `ping -c 2 8.8.8.8` | Routing/firewall; not DNS |
| DNS | `ping -c 2 ftp.debian.org` | Fix nameservers (`cat /etc/resolv.conf`) |

With **dual defaults** (`vmbr0` metric 100, `wlp2s0` metric 200): if **`vmbr0` has no carrier** but a default route via `vmbr0` still exists, traffic can break until **`net.ipv4.conf.all.ignore_routes_with_linkdown=1`** is applied (see [03-post-install-network-runbook.md](./03-post-install-network-runbook.md)). Run `sysctl -p` after edits.

Use the real Wi‑Fi interface name (e.g. **`wlp2s0`**), not the literal `WIFI` placeholder from examples.

---

## 6. Routine maintenance (typical pattern)

```bash
apt update
apt list --upgradable
```

Review the list. For **kernel / pve / qemu** updates, prefer the procedure in the **Proxmox VE Upgrade** wiki for your release (often `apt dist-upgrade` or `full-upgrade` in documented steps, sometimes with pinned phases).

**Before major upgrades:** open a maintenance window; use **console** or **out-of-band** access in case networking restarts.

---

## 7. After upgrades

- Reboot when the upgrade prompts for a **new kernel** or **PVE stack** restart.
- Confirm web UI: `https://<node-ip>:8006`
- Confirm cluster/VMs if applicable.

---

## 8. Tailscale on the Proxmox host (for automation and remote access)

Install (official script):

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Join the tailnet (pick one):

**Interactive (browser login):**

```bash
tailscale up
```

**Non-interactive (auth key from [Tailscale admin console](https://login.tailscale.com/admin/settings/keys)):**

```bash
tailscale up --auth-key='tskey-auth-REPLACE_ME' --hostname='xps-pve'
```

Verify:

```bash
tailscale status
ip -4 addr show tailscale0
```

The install script normally enables **`tailscaled`**. If needed:

```bash
systemctl enable --now tailscaled
```

Use the **Tailscale IPv4**, **MagicDNS name**, or **Serve/Funnel** only as your policy allows. Automation (Terraform, CI) typically targets **`https://<tailscale-name-or-ip>:8006`** with a valid **API token** and TLS trust configured for that endpoint.

Optional ACL/tag setup is documented on [tailscale.com](https://tailscale.com/kb/).

---

## 9. Order relative to networking runbook

If you are still building **Wi‑Fi / `vmbr0`** from [03-post-install-network-runbook.md](./03-post-install-network-runbook.md), ensure the host has **outbound HTTPS** so `curl` and `apt` work before relying on Tailscale for all access.

---

## 10. Related

- [proxmox/README.md](./README.md)
- [03-post-install-network-runbook.md](./03-post-install-network-runbook.md)
