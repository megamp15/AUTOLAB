---
tags: [gitops, github-actions, security]
status: draft
audience: operator
---

# Step 6 - GitHub Environments

GitHub Environments group secrets and optionally require approvals before sensitive workflows can run.

For the full wired secrets/variables table, see [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md).

> **Personal lab shortcut:** repository-level secrets and variables work because workflows read `secrets.NAME` and `vars.NAME` directly. The environments `autolab-plan` and `autolab-apply` must still **exist** — workflows target those names. Environment secrets are optional hardening for later.

Autolab uses two environments:

| Environment | Workflow | Purpose |
|-------------|----------|---------|
| `autolab-plan` | `opentofu-plan.yml` | Run `tofu plan` against the real Proxmox host |
| `autolab-apply` | `opentofu-apply.yml` | Run `tofu apply` — optionally protected by required reviewers |

## Repository variables

Set at **Settings → Secrets and variables → Actions → Variables**:

| Variable | Description | Example |
|----------|-------------|---------|
| `PROXMOX_HOST` | Tailscale hostname (ping checks in Packer) | `<proxmox-host>` |
| `PROXMOX_ENDPOINT` | Proxmox API URL | `https://<proxmox-host>:8006` |
| `PROXMOX_NODE_NAME` | Proxmox node name | `<proxmox-host>` |
| `PROXMOX_INSECURE_TLS` | Skip self-signed cert verification | `true` |
| `SSH_PUBLIC_KEYS` | Public SSH keys for Packer template build | `ssh-ed25519 AAAA...` |
| `PROXMOX_STORAGE_POOL` | Packer: disk storage | `local-lvm` |
| `PROXMOX_NETWORK_BRIDGE` | Packer: network bridge | `vmbr0` |
| `PACKER_ISO_URL` | Packer: pinned installer ISO URL | `https://cdimage.debian.org/debian-cd/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso` |
| `PACKER_ISO_CHECKSUM` | Packer: required ISO checksum | `sha256:65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7` |

Optional Packer variable: `PROXMOX_CLOUD_INIT_STORAGE_POOL`.

## Secrets

Set at repository or environment level:

| Secret | Used by | Notes |
|--------|---------|-------|
| `PROXMOX_API_TOKEN` | Packer, OpenTofu | Full token string. Not root password. |
| `PACKER_SSH_PASSWORD` | Packer Build | Temporary build-only password. |
| `TAILSCALE_OAUTH_CLIENT_ID` | Packer, OpenTofu | CI runner Tailscale join. |
| `TAILSCALE_OAUTH_SECRET` | Packer, OpenTofu | Shown once at creation. |
| `R2_ACCOUNT_ID` | OpenTofu | State backend. |
| `R2_ACCESS_KEY_ID` | OpenTofu | State backend. |
| `R2_SECRET_ACCESS_KEY` | OpenTofu | Shown once at creation. |
| `TAILSCALE_VM_AUTHKEY` | OpenTofu | Optional until VMs should join Tailscale. |
| `PVE_SSH_PRIVATE_KEY` | Packer Build | Optional. |

SSH keys for **cloned VMs** come from local `terraform.tfvars`
(`identity_defaults.ssh_public_keys`), not from a GitHub secret.

## If you already used repository secrets

1. Create `autolab-plan` and `autolab-apply`.
2. Run workflows with repository-level secrets/variables.
3. Later, copy secrets into environment scope if you want plan/apply separation.

## Required reviewers (Enterprise only)

Not available on Free/Team private repos. On Enterprise, add required reviewers to `autolab-apply` for approval gating before apply.

Free/Team: the manual `confirm = apply` workflow input is the gate.

## Notes

- **PROXMOX_ENDPOINT** is a variable (`https://<proxmox-host>:8006`), not a secret.
- **TAILSCALE_OAUTH_*** — create OAuth client with Keys → Auth Keys → Write, tag `tag:ci-runner`. ACL must allow `tag:ci-runner` → Proxmox on port 8006.

Sources:

- [GitHub Environments](https://docs.github.com/en/actions/deployment/using-environments-for-deployment)
- [Step 2 - Secure GitHub runner](./02-secure-runner.md)
- [Step 5 - R2 state backend](./05-r2-state-backend.md)
