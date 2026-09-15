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
| **Ansible Builder** | — | `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |
| **Tailscale Policy** | — | `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET` |

The Ansible Builder additionally reads `PROXMOX_HOST`, `PVE_EXPORTER_TOKEN_ID`
and `PVE_EXPORTER_TOKEN_SECRET` when running the `observability` playbook. They
are rendered into a `0600` file and passed as `--extra-vars @file` rather than
inline, so the token never enters the runner's process list.

Every workflow that reaches the tailnet also passes `TAILSCALE_OAUTH_CLIENT_ID`
and `TAILSCALE_OAUTH_SECRET` to the `connect-tailscale` action; the table above
lists only what each workflow reads *beyond* that runner connection.

CI authenticates to Tailscale with a **classic OAuth client ID and secret**.
`connect-tailscale` and `setup-opentofu-pipeline` both accept an OIDC audience
input, but no workflow passes one and no `TAILSCALE_OIDC_AUDIENCE` variable is
set, so the OIDC/WIF path is wired but unused. Earlier revisions of these docs
claimed Builder used OIDC/WIF with no stored secret; that was never true.

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
| `PVE_EXPORTER_TOKEN_ID` | `pve-exporter@pve!monitoring` | Ansible Builder | Proxmox read-only token ID for the hypervisor exporter. An identifier, not a credential — a variable so it stays readable in run logs. See [observability](./observability.md). |

## Secrets

Set at **Settings → Secrets and variables → Actions → Secrets** (repository-level
secrets work for a personal lab; environment secrets are optional hardening).

| Secret | Example | Used by | Where to get it |
|--------|---------|---------|-----------------|
| `PROXMOX_API_TOKEN` | `gitops@pve!opentofu=SECRET` | Packer, OpenTofu | Proxmox → Permissions → API Tokens. Shown once. |
| `TAILSCALE_OAUTH_CLIENT_ID` | `tskey-client-...` | Packer, OpenTofu, Ansible Builder, Tailscale Policy | CI-runner OAuth client ID. Paired with `TAILSCALE_OAUTH_SECRET` — **not** OIDC/WIF. Scopes: `auth_keys` owning `tag:ci-runner` (runner joins the tailnet) **and** `policy_file` (workflow 06 syncs the policy). |
| `TAILSCALE_OAUTH_SECRET` | `tskey-client-secret-...` | Packer, OpenTofu, Ansible Builder, Tailscale Policy | Secret for the CI-runner client. **Required** — it is how the runner authenticates; every tailnet-touching workflow passes it. Distinct from `TAILSCALE_VM_OAUTH_SECRET`. |
| `TAILSCALE_VM_OAUTH_CLIENT_ID` | `tskey-client-...` | OpenTofu Plan/Apply/Destroy | VM enrollment client ID; exported as `TAILSCALE_OAUTH_CLIENT_ID` into tofu steps and consumed by the destroy-time device cleanup script. |
| `TAILSCALE_VM_OAUTH_SECRET` | `tskey-client-secret-...` | OpenTofu Plan/Apply/Destroy | VM enrollment client secret; the OAuth client needs **both** `auth_keys` (Write, with `tag:autolab-vm` selected) for key minting and `devices:core` (Write) for destroy-time cleanup (see `docs/gitops/tailscale-device-lifecycle.md`). Not used by Builder. |
| `PVE_EXPORTER_TOKEN_SECRET` | `xxxxxxxx-xxxx-...` | Ansible Builder | Secret for the Proxmox read-only token. Separate from `PROXMOX_API_TOKEN`, which can create and destroy VMs; this one holds `PVEAuditor` only. Unset disables the exporter rather than shipping it broken. |
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

**Secrets**

- [ ] `PROXMOX_API_TOKEN`
- [ ] `PACKER_SSH_PASSWORD` (Packer)
- [ ] `PVE_SSH_PRIVATE_KEY` (Packer)
- [ ] `TAILSCALE_OAUTH_CLIENT_ID` + `TAILSCALE_OAUTH_SECRET` — OAuth client scoped `auth_keys` (owning `tag:ci-runner`) **and** `policy_file`
- [ ] `TAILSCALE_OAUTH_SECRET` — required; how the runner authenticates
- [ ] `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET` (OpenTofu only)
- [ ] Add the `policy_file` scope to the existing `TAILSCALE_OAUTH_CLIENT_ID` credential — no new secret; see [tailnet policy GitOps](./tailnet-policy-gitops.md)
- [ ] `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
- [ ] Ansible Builder still reuses `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`; see *Open: scope Builder's R2 access to read-only* below

### Open: scope Builder's R2 access to read-only

Workflow 05 only reads OpenTofu state (`tofu output builder_machines`) but is
given `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`, the read-write keys that
plan, apply, and destroy use to *write* state. The canary that this was waiting
on has since passed, so the work is unblocked: create an R2 API token with
**Object Read-only** scope on the state bucket and wire it in as
`BUILDER_R2_ACCESS_KEY_ID` / `BUILDER_R2_SECRET_ACCESS_KEY`.

Partially mitigated already: `setup-opentofu-pipeline` writes the keys to
`GITHUB_ENV`, which is job-wide, so every later step inherited them — including
the step that runs arbitrary Ansible against the VMs. Workflow 05 now blanks
them once the inventory is rendered, so they no longer reach the playbook.

Be accurate about what remains. Today's code never writes state, so this is not
a live defect. Narrowing the token is **defense in depth**: it protects against
a future edit, a playbook doing something unexpected, or a compromised action
in the job — cases where something other than the current code runs with those
credentials in scope.

It does **not** create a hard boundary. Any workflow can still reference
`secrets.R2_ACCESS_KEY_ID` directly, so anyone who can edit workflows can
recover write access. The value is that doing so becomes an explicit line in a
reviewable diff rather than an ambient default. The same caveat applies to
[issue #4](https://github.com/megamp15/AUTOLAB/issues/4).

**Environments**

- [ ] Optionally create `autolab-plan`, `autolab-apply` for future protection

## Related docs

- [Manual GitHub UI Packer setup](./github-ui-packer-setup.md)
- [Setup checklist](./setup-checklist.md)
- [03 - Proxmox API token](./03-proxmox-api-token.md)
- [06 - GitHub Environments](./06-github-environments.md)
- [Tailnet policy GitOps](./tailnet-policy-gitops.md)
