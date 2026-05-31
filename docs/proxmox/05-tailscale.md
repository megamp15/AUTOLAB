---
tags: [proxmox, tailscale, vpn, optional]
status: alpha
audience: operator
---

# Step 4 — Tailscale (optional, one-time)

SSH into the Proxmox host as **root** after network and `apt` work.

Adds a **second** way to reach the machine (tailnet IP / MagicDNS). LAN failover is unchanged.

## Install on the host

Official installer (review the script if you prefer not to pipe curl to sh):

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Alternative: install from Tailscale’s package repo per [their Linux docs](https://tailscale.com/download/linux).

## Join tailnet

```bash
tailscale up
```

Or with an auth key:

```bash
tailscale up --auth-key='tskey-auth-REPLACE_ME' --hostname='YOUR_NODE_NAME'
```

## Verify

```bash
tailscale status
ip -4 addr show tailscale0
systemctl is-active tailscaled
systemctl enable --now tailscaled
```

Proxmox UI over Tailscale: `https://<tailscale-ip>:8006` or `https://YOUR_NODE_NAME:8006` if MagicDNS is enabled.

## Related

- [04-apt-maintenance.md](./04-apt-maintenance.md) · [README.md](./README.md)
