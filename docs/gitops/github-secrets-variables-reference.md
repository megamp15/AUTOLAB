---
tags: [gitops, github, secrets, variables, reference]
status: draft
audience: operator
---

# GitHub Secrets & Variables Reference

Single source of truth for every secret and variable **wired into GitHub Actions today**.
If a name is not listed here, no workflow reads it.

Schema source: `infra/connection-schema.yaml` (connection) and
`infra/packer/template-schema.yaml` (Packer template vars). Fields marked
`ci_source: variable` are repository variables; `ci_source: secret` are secrets.

## What each workflow reads

| Workflow | Variables (`vars.*`) | Secrets (`secrets.*`) |
|----------|----------------------|------------------------|
| **Packer Build** | `PROXMOX_HOST`, `PROXMOX_LAN_IP`, `PROXMOX_PORT` (optional), `PROXMOX_NODE_NAME`, `PROXMOX_INSECURE_TLS`, `SSH_PUBLIC_KEYS` | `PROXMOX_API_TOKEN`, `PACKER_SSH_PASSWORD`, `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`, `PVE_SSH_PRIVATE_KEY` |
| **OpenTofu Plan** | `PROXMOX_HOST`, `PROXMOX_PORT` (optional), `PROXMOX_NODE_NAME`, `PROXMOX_INSECURE_TLS` | `PROXMOX_API_TOKEN`, `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`, `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |
| **OpenTofu Apply** | same as Plan | same as Plan |

`PROXMOX_HOST` is used for the Proxmox API endpoint and the Packer SSH bastion;
the API endpoint is derived internally with the optional `PROXMOX_PORT`.
`PROXMOX_LAN_IP` is the required PVE LAN address used only by Debian 13 builds
for their temporary PVE-local preseed server; it is distinct from
`PROXMOX_HOST` and is not part of the API connection schema.

The implemented template's release URL and checksum are owned by
`infra/packer/template-catalog.yaml` and injected by the catalog resolver; no
`PACKER_ISO_URL` or `PACKER_ISO_CHECKSUM` repository variables are used.

## Repository variables

Set at **Settings → Secrets and variables → Actions → Variables**.

| Variable | Example | Used by | Where to get it |
|----------|---------|---------|-----------------|
| `PROXMOX_HOST` | `<proxmox-host>` | Packer Build | Tailscale MagicDNS name. `hostname` on Proxmox host. |
| `PROXMOX_LAN_IP` | `192.168.1.10` | Packer Build | Required PVE LAN IP reachable by the temporary Debian installer VM. |
| `PROXMOX_PORT` | `8006` | Packer, OpenTofu | Optional API HTTPS port override. |
| `PROXMOX_NODE_NAME` | `<proxmox-host>` | Packer, OpenTofu | Proxmox UI left sidebar (not always `pve`). |
| `PROXMOX_INSECURE_TLS` | `true` | Packer, OpenTofu | Keep `true` for Proxmox default self-signed cert. |
| `SSH_PUBLIC_KEYS` | `ssh-ed25519 AAAA...` | Packer Build | `cat ~/.ssh/id_ed25519.pub` on your laptop. |

## Secrets

Set at **Settings → Secrets and variables → Actions → Secrets** (repository-level
secrets work for a personal lab; environment secrets are optional hardening).

| Secret | Example | Used by | Where to get it |
|--------|---------|---------|-----------------|
| `PROXMOX_API_TOKEN` | `gitops@pve!opentofu=SECRET` | Packer, OpenTofu | Proxmox → Permissions → API Tokens. Shown once. |
| `PACKER_SSH_PASSWORD` | generated password | Packer Build | Temporary build-only password. Not your SSH key. |
| `TAILSCALE_OAUTH_CLIENT_ID` | `tskey-client-...` | Packer, OpenTofu | Tailscale → Settings → OAuth clients. |
| `TAILSCALE_OAUTH_SECRET` | `tskey-client-secret-...` | Packer, OpenTofu | Same screen. Shown once. |
| `TAILSCALE_VM_OAUTH_CLIENT_ID` | `tskey-client-...` | OpenTofu | OAuth client with the `auth_keys` scope for per-VM enrollment. |
| `TAILSCALE_VM_OAUTH_SECRET` | `tskey-client-secret-...` | OpenTofu | Matching VM enrollment OAuth client secret. |
| `R2_ACCOUNT_ID` | `a1b2c3...` | OpenTofu | Cloudflare dashboard URL / R2 page. |
| `R2_ACCESS_KEY_ID` | `abc123...` | OpenTofu | R2 → Manage API Tokens. Shown once. |
| `R2_SECRET_ACCESS_KEY` | `xyz789...` | OpenTofu | Same. Shown once. |
| `PVE_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH...` | Packer Build | Required. Packer uses it as the SSH bastion key for `PROXMOX_HOST`. |

## Local-only config (not GitHub)

These are **not** injected by CI today:

| File | Field | Purpose |
|------|-------|---------|
| `infra/stacks/lab/terraform.tfvars` | `machines` | Which VMs/LXCs to create. Defaults to `{}` → plan shows no changes. |
| `infra/stacks/lab/terraform.tfvars` | `identity_defaults.ssh_public_keys` | SSH key for cloned VMs (OpenTofu cloud-init). Separate from `SSH_PUBLIC_KEYS`. |

Copy from `infra/stacks/lab/terraform.tfvars.example` and edit locally.
`terraform.tfvars` is gitignored.

## Packer Build and machine lifecycle

1. **Packer Build** → creates a Debian `9000` or Ubuntu `9001` template candidate.
2. Use the [template lifecycle](./template-lifecycle.md) for the staged
   `template-validation`, `integration-test`, and `lab` process.
3. Normal machine changes are written to git and applied by protected GitHub
   Actions with R2-backed state. Do not use local `tofu apply` or `tofu destroy`
   for normal operation.

## GitHub Environments (must exist)

| Environment | Workflow |
|-------------|----------|
| `autolab-plan` | `opentofu-plan.yml` |
| `autolab-apply` | `opentofu-apply.yml` |

Environments must exist even if secrets live at repository level.

## Quick checklist

**Variables**

- [ ] `PROXMOX_HOST`
- [ ] `PROXMOX_LAN_IP` (required for Debian 13 Packer Build)
- [ ] `PROXMOX_PORT` (optional; defaults to `8006`)
- [ ] `PROXMOX_NODE_NAME`
- [ ] `PROXMOX_INSECURE_TLS` = `true`
- [ ] `SSH_PUBLIC_KEYS`

**Secrets**

- [ ] `PROXMOX_API_TOKEN`
- [ ] `PACKER_SSH_PASSWORD` (Packer)
- [ ] `PVE_SSH_PRIVATE_KEY` (Packer)
- [ ] `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`
- [ ] `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET` (OAuth `auth_keys` scope)
- [ ] `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`

**Environments**

- [ ] `autolab-plan`, `autolab-apply`

## Related docs

- [Manual GitHub UI Packer setup](./github-ui-packer-setup.md)
- [Setup checklist](./setup-checklist.md)
- [03 - Proxmox API token](./03-proxmox-api-token.md)
- [06 - GitHub Environments](./06-github-environments.md)
