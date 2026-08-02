---
tags: [gitops, github-actions, security]
status: draft
audience: operator
---

# Step 6 - GitHub Environments

GitHub Environments group secrets and optionally require approvals before sensitive workflows can run.

For the full wired secrets/variables table, see [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md).
For the manual Packer entry and PVE SSH bastion setup, see [Manual GitHub UI Packer setup](./github-ui-packer-setup.md).

> **Personal lab setup:** repository-level secrets and variables are read directly by the workflows. The current Plan, Apply, and Destroy workflows do not target a GitHub Environment; typed confirmations and the `opentofu-state` concurrency guard remain active. GitHub Environments may be added later if environment-scoped protection is required.

Autolab uses two environments:

| Environment | Workflow | Purpose |
|-------------|----------|---------|
| `autolab-plan` | Not targeted | No current workflow assignment |
| `autolab-apply` | Not targeted | No current workflow assignment; Apply/Destroy retain typed confirmations |

## Repository variables

Set at **Settings → Secrets and variables → Actions → Variables**:

| Variable | Description | Example |
|----------|-------------|---------|
| `PROXMOX_HOST` | Proxmox host name/IP used by OpenTofu and the Packer bastion | `<proxmox-host>` |
| `PROXMOX_PORT` | Optional Proxmox API HTTPS port; defaults to `8006` | `8006` |
| `PROXMOX_NODE_NAME` | Proxmox node name | `<proxmox-host>` |
| `PROXMOX_INSECURE_TLS` | Skip self-signed cert verification | `true` |
| `PROXMOX_PACKER_NETWORK_BRIDGE` | Required bridge for the temporary Packer VM; no `vmbr0` fallback | `vmbr1` |
| `SSH_PUBLIC_KEYS` | Public SSH keys for Packer template build | `ssh-ed25519 AAAA...` |

The Debian Packer release URL and checksum come from the selected entry in
`infra/packer/template-catalog.yaml`; they are not GitHub repository variables.

Packer uses `local-lvm`, `vmbr0`, and its selected storage defaults internally;
these are not GitHub variables. The internal API endpoint is derived as
`https://${PROXMOX_HOST}:${PROXMOX_PORT}` (with IPv6 literals bracketed).

## Secrets

Set at repository or environment level:

| Secret | Used by | Notes |
|--------|---------|-------|
| `PROXMOX_API_TOKEN` | Packer, OpenTofu | Full token string. Not root password. |
| `PACKER_SSH_PASSWORD` | Packer Build | Temporary build-only password. |
| `TAILSCALE_OAUTH_CLIENT_ID` | Packer, OpenTofu | CI runner OAuth client; runner tag is `tag:ci-runner`. |
| `TAILSCALE_OAUTH_SECRET` | Packer, OpenTofu | Matching runner OAuth client secret. |
| `TAILSCALE_VM_OAUTH_CLIENT_ID` | OpenTofu only | Separate OAuth client with `auth_keys` scope for VM enrollment. |
| `TAILSCALE_VM_OAUTH_SECRET` | OpenTofu only | Matching VM enrollment OAuth client secret; not for the CI runner. |
| `R2_ACCOUNT_ID` | OpenTofu | State backend. |
| `R2_ACCESS_KEY_ID` | OpenTofu | State backend. |
| `R2_SECRET_ACCESS_KEY` | OpenTofu | Shown once at creation. |
| `PVE_SSH_PRIVATE_KEY` | Packer Build | Required SSH bastion key for hosted builds. |

SSH keys for **cloned VMs** come from local `terraform.tfvars`
(`identity_defaults.ssh_public_keys`), not from a GitHub secret.

## If you already used repository secrets

1. Optionally create `autolab-plan` and `autolab-apply` for future environment-scoped protection.
2. Run workflows with repository-level secrets/variables.
3. Add environment assignments later if plan/apply separation is required.

## Required reviewers (Enterprise only)

Not available on Free/Team private repos. On Enterprise, add required reviewers to `autolab-apply` for approval gating before apply.

Free/Team: the manual `confirm = apply` workflow input is the gate.

## Notes

- **PROXMOX_PORT** is optional and defaults to `8006`; the API endpoint is derived internally.
- **TAILSCALE_OAUTH_*** — create OAuth client with Keys → Auth Keys → Write, tag `tag:ci-runner`. ACL must allow `tag:ci-runner` → Proxmox on port 8006.
- **TAILSCALE_VM_OAUTH_*** — create a separate OAuth client with the `auth_keys` scope. OpenTofu creates one non-reusable, preauthorized key per builder VM with `tag:autolab-vm`; configure that tag in the owner/policy ACL for VM access.

Sources:

- [GitHub Environments](https://docs.github.com/en/actions/deployment/using-environments-for-deployment)
- [Step 2 - Secure GitHub runner](./02-secure-runner.md)
- [Step 5 - R2 state backend](./05-r2-state-backend.md)
