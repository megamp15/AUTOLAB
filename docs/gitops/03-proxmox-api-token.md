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
- Store the token in a GitHub secret.
- Rotate the token if it is exposed.
- Never commit the token, real tfvars, state, or generated plans.

## GitHub names (wired today)

See [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md) for the full list.

### Variables

| Variable | Meaning |
|----------|---------|
| `PROXMOX_HOST` | Tailscale hostname (Packer ping checks) |
| `PROXMOX_ENDPOINT` | API URL, e.g. `https://<proxmox-host>:8006` |
| `PROXMOX_NODE_NAME` | Node name from Proxmox UI |
| `PROXMOX_INSECURE_TLS` | `true` for default self-signed cert |

### Secrets

| Secret | Meaning |
|--------|---------|
| `PROXMOX_API_TOKEN` | Full API token string |

SSH public keys for cloned VMs are set in local `terraform.tfvars`
(`identity_defaults.ssh_public_keys`), not in a GitHub secret. Packer template
builds use the `SSH_PUBLIC_KEYS` repository variable.

Source:

- [Proxmox VE administration guide](https://pve.proxmox.com/pve-docs/pve-admin-guide.html)
