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
| **Packer Build** | `PROXMOX_ENDPOINT`, `PROXMOX_NODE_NAME`, `PROXMOX_INSECURE_TLS`, `PROXMOX_HOST`, `PROXMOX_STORAGE_POOL`, `PROXMOX_NETWORK_BRIDGE`, `PACKER_ISO_URL`, `PACKER_ISO_CHECKSUM`, `PROXMOX_CLOUD_INIT_STORAGE_POOL`, `SSH_PUBLIC_KEYS` | `PROXMOX_API_TOKEN`, `PACKER_SSH_PASSWORD`, `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`, `PVE_SSH_PRIVATE_KEY` (optional) |
| **OpenTofu Plan** | `PROXMOX_ENDPOINT`, `PROXMOX_NODE_NAME`, `PROXMOX_INSECURE_TLS` | `PROXMOX_API_TOKEN`, `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `TAILSCALE_VM_AUTHKEY` (optional) |
| **OpenTofu Apply** | same as Plan | same as Plan |

`PROXMOX_HOST` is only used for Tailscale ping / ssh-keyscan in Packer Build — not
passed to the Proxmox API.

## Repository variables

Set at **Settings → Secrets and variables → Actions → Variables**.

| Variable | Example | Used by | Where to get it |
|----------|---------|---------|-----------------|
| `PROXMOX_HOST` | `<proxmox-host>` | Packer Build | Tailscale MagicDNS name. `hostname` on Proxmox host. |
| `PROXMOX_ENDPOINT` | `https://<proxmox-host>:8006` | Packer, OpenTofu | `https://<proxmox-host>:8006` |
| `PROXMOX_NODE_NAME` | `<proxmox-host>` | Packer, OpenTofu | Proxmox UI left sidebar (not always `pve`). |
| `PROXMOX_INSECURE_TLS` | `true` | Packer, OpenTofu | Keep `true` for Proxmox default self-signed cert. |
| `SSH_PUBLIC_KEYS` | `ssh-ed25519 AAAA...` | Packer Build | `cat ~/.ssh/id_ed25519.pub` on your laptop. |
| `PROXMOX_STORAGE_POOL` | `local-lvm` | Packer Build | Proxmox → Datacenter → Storage. |
| `PROXMOX_NETWORK_BRIDGE` | `vmbr0` | Packer Build | Proxmox → Node → Network. |
| `PACKER_ISO_URL` | `https://cdimage.debian.org/debian-cd/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso` | Packer Build | Pinned ISO URL downloaded directly by Proxmox. |
| `PACKER_ISO_CHECKSUM` | `sha256:65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7` | Packer Build | Required SHA-256 checksum for the pinned ISO. |
| `PROXMOX_CLOUD_INIT_STORAGE_POOL` | `local-lvm` | Packer Build | Optional. Defaults to `PROXMOX_STORAGE_POOL`. |

## Secrets

Set at **Settings → Secrets and variables → Actions → Secrets** (repository-level
secrets work for a personal lab; environment secrets are optional hardening).

| Secret | Example | Used by | Where to get it |
|--------|---------|---------|-----------------|
| `PROXMOX_API_TOKEN` | `gitops@pve!opentofu=SECRET` | Packer, OpenTofu | Proxmox → Permissions → API Tokens. Shown once. |
| `PACKER_SSH_PASSWORD` | generated password | Packer Build | Temporary build-only password. Not your SSH key. |
| `TAILSCALE_OAUTH_CLIENT_ID` | `tskey-client-...` | Packer, OpenTofu | Tailscale → Settings → OAuth clients. |
| `TAILSCALE_OAUTH_SECRET` | `tskey-client-secret-...` | Packer, OpenTofu | Same screen. Shown once. |
| `R2_ACCOUNT_ID` | `a1b2c3...` | OpenTofu | Cloudflare dashboard URL / R2 page. |
| `R2_ACCESS_KEY_ID` | `abc123...` | OpenTofu | R2 → Manage API Tokens. Shown once. |
| `R2_SECRET_ACCESS_KEY` | `xyz789...` | OpenTofu | Same. Shown once. |
| `TAILSCALE_VM_AUTHKEY` | `tskey-auth-...` | OpenTofu | Optional. VMs join Tailscale via `terraform.tfvars` + this secret. |
| `PVE_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH...` | Packer Build | Optional. Only if Packer needs SSH to the Proxmox host. |

## Local-only config (not GitHub)

These are **not** injected by CI today:

| File | Field | Purpose |
|------|-------|---------|
| `infra/stacks/lab/terraform.tfvars` | `machines` | Which VMs/LXCs to create. Defaults to `{}` → plan shows no changes. |
| `infra/stacks/lab/terraform.tfvars` | `identity_defaults.ssh_public_keys` | SSH key for cloned VMs (OpenTofu cloud-init). Separate from `SSH_PUBLIC_KEYS`. |

Copy from `infra/stacks/lab/terraform.tfvars.example` and edit locally.
`terraform.tfvars` is gitignored.

## Creating a test VM

1. **Packer Build** → creates template VM `9000` (`debian-13`)
2. **OpenTofu Plan** → smoke test (expect no changes until `machines` is set locally)
3. **Local `tofu apply`** with `terraform.tfvars` → creates the disposable VM
4. Destroy the VM when done; keep the template

## GitHub Environments (must exist)

| Environment | Workflow |
|-------------|----------|
| `autolab-plan` | `opentofu-plan.yml` |
| `autolab-apply` | `opentofu-apply.yml` |

Environments must exist even if secrets live at repository level.

## Quick checklist

**Variables**

- [ ] `PROXMOX_HOST`
- [ ] `PROXMOX_ENDPOINT` = `https://<proxmox-host>:8006`
- [ ] `PROXMOX_NODE_NAME`
- [ ] `PROXMOX_INSECURE_TLS` = `true`
- [ ] `SSH_PUBLIC_KEYS`
- [ ] `PROXMOX_STORAGE_POOL`, `PROXMOX_NETWORK_BRIDGE`, `PACKER_ISO_URL` (Packer)
- [ ] `PACKER_ISO_CHECKSUM` = `sha256:65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7` (Packer)

**Secrets**

- [ ] `PROXMOX_API_TOKEN`
- [ ] `PACKER_SSH_PASSWORD` (Packer)
- [ ] `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`
- [ ] `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`

**Environments**

- [ ] `autolab-plan`, `autolab-apply`

## Related docs

- [Setup checklist](./setup-checklist.md)
- [03 - Proxmox API token](./03-proxmox-api-token.md)
- [06 - GitHub Environments](./06-github-environments.md)
