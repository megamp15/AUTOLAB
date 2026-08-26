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
| **Packer Build** | `PROXMOX_HOST`, `PROXMOX_LAN_IP`, `PROXMOX_PACKER_NETWORK_BRIDGE`, `PROXMOX_PORT` (optional), `PROXMOX_NODE_NAME`, `PROXMOX_INSECURE_TLS`, `SSH_PUBLIC_KEYS` | `PROXMOX_API_TOKEN`, `PACKER_SSH_PASSWORD`, `PVE_SSH_PRIVATE_KEY` |
| **OpenTofu Plan** | `PROXMOX_HOST`, `PROXMOX_PORT` (optional), `PROXMOX_NODE_NAME`, `PROXMOX_INSECURE_TLS` | `PROXMOX_API_TOKEN`, `PVE_SSH_PRIVATE_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |
| **OpenTofu Apply/Destroy** | same as Plan | same as Plan |
| **Ansible Builder** | `TAILSCALE_OIDC_AUDIENCE` | `TAILSCALE_OAUTH_CLIENT_ID`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |

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
| `PROXMOX_PACKER_NETWORK_BRIDGE` | `vmbr1` | Packer Build | Required Proxmox bridge for the temporary Packer VM; there is no workflow fallback. |
| `PROXMOX_PORT` | `8006` | Packer, OpenTofu | Optional API HTTPS port override. |
| `PROXMOX_NODE_NAME` | `<proxmox-host>` | Packer, OpenTofu | Proxmox UI left sidebar (not always `pve`). |
| `PROXMOX_INSECURE_TLS` | `true` | Packer, OpenTofu | Keep `true` for Proxmox default self-signed cert. |
| `SSH_PUBLIC_KEYS` | `ssh-ed25519 AAAA...` | Packer Build | `cat ~/.ssh/id_ed25519.pub` on your laptop. |
| `TAILSCALE_OIDC_AUDIENCE` | `https://tailscale.com/...` | Ansible Builder | Non-secret GitHub OIDC/WIF audience for the existing Tailscale client ID. |

## Secrets

Set at **Settings → Secrets and variables → Actions → Secrets** (repository-level
secrets work for a personal lab; environment secrets are optional hardening).

| Secret | Example | Used by | Where to get it |
|--------|---------|---------|-----------------|
| `PROXMOX_API_TOKEN` | `gitops@pve!opentofu=SECRET` | Packer, OpenTofu | Proxmox → Permissions → API Tokens. Shown once. |
| `TAILSCALE_OAUTH_CLIENT_ID` | `tskey-client-...` | Ansible Builder | Existing client ID used with GitHub OIDC/WIF; no OAuth secret is used for Builder. |
| `TAILSCALE_VM_OAUTH_CLIENT_ID` | `tskey-client-...` | OpenTofu Plan/Apply/Destroy | VM enrollment client ID; exported as `TAILSCALE_OAUTH_CLIENT_ID` into tofu steps and consumed by the destroy-time device cleanup script. |
| `TAILSCALE_VM_OAUTH_SECRET` | `tskey-client-secret-...` | OpenTofu Plan/Apply/Destroy | VM enrollment client secret; OAuth client must be scoped `devices:core:read_write` ONLY (see `docs/gitops/tailscale-device-lifecycle.md`). Not used by Builder. |
| `PACKER_SSH_PASSWORD` | generated password | Packer Build | Temporary build-only password. Not your SSH key. |
| `R2_ACCOUNT_ID` | `a1b2c3...` | OpenTofu | Cloudflare dashboard URL / R2 page. |
| `R2_ACCESS_KEY_ID` | `abc123...` | OpenTofu | R2 → Manage API Tokens. Shown once. |
| `R2_SECRET_ACCESS_KEY` | `xyz789...` | OpenTofu | Same. Shown once. |
| `PVE_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH...` | Packer Build | Required only as the Proxmox bastion key; never reuse it for a VM. |

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

## GitHub Environments (optional)

| Environment | Workflow |
|-------------|----------|
| `autolab-plan` | Not targeted by current workflows |
| `autolab-apply` | Not targeted by current workflows |

The current workflows use repository-level secrets and typed workflow
confirmations; they do not assign a GitHub Environment. These environments may
be retained for future protection, but are not required for the workflows to
read repository secrets.

## Quick checklist

**Variables**

- [ ] `PROXMOX_HOST`
- [ ] `PROXMOX_LAN_IP` (required for Debian 13 Packer Build)
- [ ] `PROXMOX_PORT` (optional; defaults to `8006`)
- [ ] `PROXMOX_NODE_NAME`
- [ ] `PROXMOX_INSECURE_TLS` = `true`
- [ ] `PROXMOX_PACKER_NETWORK_BRIDGE`
- [ ] `SSH_PUBLIC_KEYS`
- [ ] `TAILSCALE_OIDC_AUDIENCE` (non-secret)

**Secrets**

- [ ] `PROXMOX_API_TOKEN`
- [ ] `PACKER_SSH_PASSWORD` (Packer)
- [ ] `PVE_SSH_PRIVATE_KEY` (Packer)
- [ ] `TAILSCALE_OAUTH_CLIENT_ID` with GitHub OIDC/WIF trust binding for `tag:ci-runner`
- [ ] `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET` (OpenTofu only)
- [ ] `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
- [ ] Ansible Builder temporarily reuses `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` for canary validation

> **TODO after successful canary validation:** introduce
> `BUILDER_R2_ACCESS_KEY_ID` and `BUILDER_R2_SECRET_ACCESS_KEY` as Builder
> Environment secrets with Object Read-only scope on the existing state bucket.

**Environments**

- [ ] Optionally create `autolab-plan`, `autolab-apply` for future protection

## Related docs

- [Manual GitHub UI Packer setup](./github-ui-packer-setup.md)
- [Setup checklist](./setup-checklist.md)
- [03 - Proxmox API token](./03-proxmox-api-token.md)
- [06 - GitHub Environments](./06-github-environments.md)
