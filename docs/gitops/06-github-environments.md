---
tags: [gitops, github-actions, security]
status: draft
audience: operator
---

# Step 6 - GitHub Environments

GitHub Environments group secrets and optionally require approvals before sensitive workflows can run.

Autolab uses two environments:

| Environment | Workflow | Purpose |
|-------------|----------|---------|
| `autolab-plan` | `opentofu-plan.yml` | Run `tofu plan` against the real Proxmox host |
| `autolab-apply` | `opentofu-apply.yml` | Run `tofu apply` — optionally protected by required reviewers |

## Repository Variables (non-sensitive)

These are set at the repository or organization level, not in environments:

| Variable | Description | Example |
|----------|-------------|---------|
| `PROXMOX_HOST` | Proxmox Tailscale hostname | `xps-pve` |
| `PROXMOX_NODE_NAME` | Proxmox node name | `pve` |
| `SSH_PUBLIC_KEYS` | SSH public keys for VM/LXC injection (comma-separated) | `ssh-ed25519 AAAA... autolab@example` |

These align with the connection schema's `ci_env`/`ci_source` vocabulary: values marked `ci_source: variable` are read from repository variables, while values marked `ci_source: secret` are read from environment secrets.

## Secrets per environment

Both environments share the same set of secrets:

| Secret | Description |
|--------|-------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | Tailscale OAuth client ID for CI runners |
| `TAILSCALE_OAUTH_SECRET` | Tailscale OAuth client secret for CI runners |
| `PROXMOX_ENDPOINT` | Proxmox API endpoint — use the Tailscale hostname (e.g. `https://xps-pve:8006`) |
| `PROXMOX_API_TOKEN` | Proxmox API token value |
| `R2_ACCOUNT_ID` | Cloudflare account ID for R2 endpoint |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key for state backend |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret key for state backend |
| `AUTOLAB_ADMIN_SSH_PUBLIC_KEY` | SSH public key injected into VMs and LXCs |
| `TAILSCALE_VM_AUTHKEY` | Tailscale auth key for VMs to join the tailnet (ephemeral, reusable, tagged for VMs) |

The generated `.github/actions/configure-proxmox-connection` action consumes this schema-driven mapping and exports the correct CI environment for OpenTofu and Packer jobs.

## Creating environments

1. Go to your GitHub repository → **Settings** → **Environments**.
2. Click **New environment** and name it `autolab-plan`.
3. Repeat for `autolab-apply`.

## Adding secrets to an environment

1. Open the environment page.
2. Under **Environment secrets**, click **Add secret**.
3. Add each secret from the table above.
4. The `TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_SECRET` are OAuth client credentials (see [Step 2 - Secure GitHub runner](./02-secure-runner.md) for setup instructions).

## Required reviewers (optional)

For extra safety, add required reviewers to `autolab-apply`:

1. Open the `autolab-apply` environment page.
2. Under **Deployment branches**, choose **Selected branches** and add your default branch (e.g. `main`).
3. Under **Required reviewers**, add yourself or your team.

When required reviewers are set, any workflow run that targets the `autolab-apply` environment will pause and wait for an approved review before proceeding.

## Notes

- **PROXMOX_ENDPOINT** should use the Tailscale hostname (e.g. `https://xps-pve:8006`) rather than a public IP or public DNS name. The GitHub runner connects via Tailscale, so it resolves Tailscale MagicDNS hostnames natively.
- **TAILSCALE_OAUTH_CLIENT_ID** and **TAILSCALE_OAUTH_SECRET** are preferred over auth keys because they don't require rotation. Create an OAuth client in the Tailscale admin console under Settings → OAuth clients. The client needs permission to create ephemeral nodes with the `tag:ci-runner` tag. The Tailscale ACL must allow traffic from that tag to the Proxmox host on port 8006.

Sources:

- [GitHub Environments](https://docs.github.com/en/actions/deployment/using-environments-for-deployment)
- [Step 2 - Secure GitHub runner](./02-secure-runner.md)
- [Step 5 - R2 state backend](./05-r2-state-backend.md)
