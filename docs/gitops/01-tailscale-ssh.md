---
tags: [gitops, tailscale, ssh, security]
status: draft
audience: beginner
---

# Step 1 - Tailscale SSH

You already joined the Proxmox host to Tailscale in phase 1. That gives the host a private tailnet address, but it does not automatically enable Tailscale SSH.

Tailscale has two SSH patterns:

| Pattern | Uses your SSH keys? | Best for |
|---------|---------------------|----------|
| OpenSSH over Tailscale | Yes | GitOps automation, Ansible, fallback access |
| Tailscale SSH | Not usually | Human admin access controlled by tailnet identity and ACLs |

Autolab uses both:

- Human access: Tailscale SSH.
- Automation access: normal SSH key auth over the Tailscale network.

## Enable Tailscale SSH on a Linux host

On the host:

```bash
sudo tailscale set --ssh
```

Or when joining a new machine:

```bash
sudo tailscale up --ssh
```

Verify:

```bash
tailscale status
tailscale ip -4
```

From your laptop:

```bash
tailscale ssh USER@HOSTNAME
```

`HOSTNAME` can be the MagicDNS name or the Tailscale IP.

## Tailnet policy

Tailscale SSH is controlled by the tailnet policy file, not by `authorized_keys`.

Start with a conservative policy:

- allow your owner/admin identity to SSH to tagged lab servers
- allow non-root users only
- require check mode for privileged access if you want extra confirmation

Example shape:

```json
{
  "ssh": [
    {
      "action": "accept",
      "src": ["autogroup:admin"],
      "dst": ["tag:autolab"],
      "users": ["autogroup:nonroot"]
    }
  ]
}
```

Keep this in the Tailscale admin console first. Later, it can be versioned through a separate tailnet policy workflow.

## Security notes

- Tailscale SSH does not replace every use of OpenSSH.
- It does not modify `/etc/ssh/sshd_config` or `~/.ssh/authorized_keys`.
- Keep a tested fallback path while learning.
- Do not allow root login by default.
- Do not expose SSH from lab machines to the public internet.

Sources:

- [Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh)
- [Tailnet policy syntax](https://tailscale.com/kb/1337/acl-syntax/)
