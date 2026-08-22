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
| `TAILSCALE_OIDC_AUDIENCE` | Non-secret GitHub OIDC/WIF audience for the existing Tailscale client ID | `https://tailscale.com/...` |

The Debian Packer release URL and checksum come from the selected entry in
`infra/packer/template-catalog.yaml`; they are not GitHub repository variables.

Packer uses `local-lvm`, `vmbr0`, and its selected storage defaults internally;
these are not GitHub variables. The internal API endpoint is derived as
`https://${PROXMOX_HOST}:${PROXMOX_PORT}` (with IPv6 literals bracketed).

Add the non-secret variable `TAILSCALE_OIDC_AUDIENCE` for the existing
`TAILSCALE_OAUTH_CLIENT_ID` WIF configuration. Builder CI does not use an
OAuth client secret.

## Secrets

Set at repository or environment level:

| Secret | Used by | Notes |
|--------|---------|-------|
| `PROXMOX_API_TOKEN` | Packer, OpenTofu | Full token string. Not root password. |
| `PACKER_SSH_PASSWORD` | Packer Build | Temporary build-only password. |
| `R2_ACCOUNT_ID` | OpenTofu | State backend. |
| `R2_ACCESS_KEY_ID` | OpenTofu | State backend. |
| `R2_SECRET_ACCESS_KEY` | OpenTofu | Shown once at creation. |
| `TAILSCALE_OAUTH_CLIENT_ID` | Builder | Existing client ID used with GitHub OIDC/WIF. |
| `TAILSCALE_VM_OAUTH_CLIENT_ID` | OpenTofu Plan/Apply | VM enrollment client ID. |
| `TAILSCALE_VM_OAUTH_SECRET` | OpenTofu Plan/Apply | VM enrollment client secret; not used by Builder CI. |
| `PVE_SSH_PRIVATE_KEY` | Packer Build | Required only as the Proxmox SSH bastion key; never reuse it for VMs. |

SSH keys for **cloned VMs** come from local `terraform.tfvars`
(`identity_defaults.ssh_public_keys`), not from a GitHub secret.

For initial Builder canary validation, reuse the existing `R2_ACCOUNT_ID`,
`R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`. Do not require separate
Builder credentials yet.

> **TODO after successful canary validation:** add
> `BUILDER_R2_ACCESS_KEY_ID` and `BUILDER_R2_SECRET_ACCESS_KEY` with R2 Object
> Read-only access to the existing state bucket. Reuse `R2_ACCOUNT_ID`; do not
> create a second account or bucket.

## If you already used repository secrets

1. Optionally create `autolab-plan` and `autolab-apply` for future environment-scoped protection.
2. Run workflows with repository-level secrets/variables.
3. Add environment assignments later if plan/apply separation is required.

## Required reviewers (Enterprise only)

Not available on Free/Team private repos. On Enterprise, add required reviewers to `autolab-apply` for approval gating before apply.

Free/Team: the manual `confirm = apply` workflow input is the gate.

## Notes

- **PROXMOX_PORT** is optional and defaults to `8006`; the API endpoint is derived internally.
- **GitHub OIDC/WIF** — bind the approved workflow identity to `tag:ci-runner`; no OAuth client secret is stored in GitHub.
- **Builder enrollment** — before replacing a VM, retire its old `tag:autolab-vm` device first so the stable MagicDNS target is not suffixed or left stale. OpenTofu manages a short-lived, reusable-per-VM enrollment key in remote state; Terraform does not automatically clean up Tailscale devices.

Sources:

- [GitHub Environments](https://docs.github.com/en/actions/deployment/using-environments-for-deployment)
- [Step 2 - Secure GitHub runner](./02-secure-runner.md)
- [Step 5 - R2 state backend](./05-r2-state-backend.md)
