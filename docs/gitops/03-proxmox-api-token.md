---
tags: [gitops, proxmox, api-token, security]
status: draft
audience: operator
---

# Step 3 - Proxmox API token

OpenTofu needs Proxmox API access to create VMs and LXCs.

Do not use your personal root password in GitHub Actions.

## Recommended identity split

| Identity | Where | Purpose |
|----------|-------|---------|
| Human admin user | VM/LXC Linux OS | Your personal admin access |
| `gitops` deploy user | VM/LXC Linux OS | Ansible and automation access |
| GitHub runner user | Runner OS | Runs Actions jobs without being root |
| Proxmox API token | Proxmox | Lets OpenTofu create and update resources |

## API token rules

- Create a dedicated Proxmox user for automation.
- Create a token for that user.
- Grant only the permissions needed for the lab resource pool/storage/node.
- Store the token in a GitHub Environment secret or runner-local secret store.
- Rotate the token if it is exposed.
- Never commit the token, real tfvars, state, or generated plans.

## Suggested secret names

### Repository Variables (non-sensitive)

Set these at the repository or organization level:

| Variable | Meaning |
|----------|---------|
| `PROXMOX_HOST` | Proxmox Tailscale hostname (e.g. `xps-pve`) |
| `PROXMOX_NODE_NAME` | Proxmox node name (e.g. `pve`) |

### Environment Secrets (sensitive)

Store these in GitHub Environments:

| Secret | Meaning |
|--------|---------|
| `PROXMOX_ENDPOINT` | Example: `https://xps-pve:8006` (use Tailscale hostname) |
| `PROXMOX_API_TOKEN` | Provider token value |
| `AUTOLAB_ADMIN_SSH_PUBLIC_KEY` | Public key injected into VMs/LXCs |
| `TAILSCALE_OAUTH_CLIENT_ID` | Tailscale OAuth client ID for CI runners |
| `TAILSCALE_OAUTH_SECRET` | Tailscale OAuth client secret for CI runners |
| `R2_ACCOUNT_ID` | Cloudflare account ID for R2 endpoint |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key for state backend |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret key for state backend |

The private SSH key for automation should be handled separately in phase 2C when Ansible is added.

Source:

- [Proxmox VE administration guide](https://pve.proxmox.com/pve-docs/pve-admin-guide.html)
