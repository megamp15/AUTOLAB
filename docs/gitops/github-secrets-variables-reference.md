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
| **OpenTofu Plan** | `CLOUDFLARE_ACCOUNT_ID`, `PROXMOX_HOST`, `PROXMOX_PORT` (optional), `PROXMOX_NODE_NAME`, `PROXMOX_INSECURE_TLS`, `TAILSCALE_VM_TAG` (optional), `BUILDER_SSH_PUBLIC_KEY` (tenant stacks) | `PROXMOX_API_TOKEN`, `PVE_SSH_PRIVATE_KEY`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET` |
| **OpenTofu Apply/Destroy** | same as Plan | same as Plan |
| **Cloudflare** | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_ZONE_ID` | `CLOUDFLARE_API_TOKEN`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |
| **Ansible Builder** | `CLOUDFLARE_ACCOUNT_ID`, `INGRESS_ACME_EMAIL`, `POCKET_ID_ADMIN_USER`, `BUILDER_SSH_PUBLIC_KEY` (optional) | `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `BUILDER_SSH_PRIVATE_KEY` (tenant stacks) |
| **Tailscale Policy** | — | `TAILSCALE_OAUTH_CLIENT_ID`, `TAILSCALE_OAUTH_SECRET` |

The Ansible Builder additionally reads `PROXMOX_HOST`, `PVE_EXPORTER_TOKEN_ID`,
`PVE_EXPORTER_TOKEN_SECRET`, `NTFY_TOPIC` and `GF_SECURITY_ADMIN_PASSWORD`
when running the `observability`
playbook. They are rendered into a `0600` file and passed as
`--extra-vars @file` rather than inline, so no secret enters the runner's
process list.

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
| `TAILSCALE_VM_TAG` | `tag:qnta-vm` | OpenTofu Plan/Apply/Destroy | **Environment-level**, on a tenant's environment only. The tag its VMs enrol under and the only tag the destroy-time cleanup may delete. Unset, the provider's `tag:autolab-vm` applies. See [tenants](./tenants.md). |
| `BUILDER_SSH_PUBLIC_KEY` | `ssh-ed25519 AAAA... autolab-builder` | OpenTofu (tenant stacks), Ansible Builder | Public half of the Builder keypair. cloud-init places it on tenant VMs' break-glass user; the `gitops-user` role installs it for `gitops` everywhere. Provider-owned: one key serves every tenant. Generate with `ssh-keygen -t ed25519 -f ~/.ssh/autolab-builder -N '' -C autolab-builder`. |
| `NAS_SERVER` | `192.168.50.163` | OpenTofu Plan/Apply/Destroy | **Environment-level.** Default server for `builder.storage` entries that omit one. Over the LAN, the address the router reserves for the NAS; over the tailnet, its MagicDNS name. |
| `NAS_SMB_USERNAME` | `qnta` | Ansible Builder (`storage`) | **Environment-level.** The NAS account SMB mounts naming credential `nas` authenticate as. One per tenant, with rights on that tenant's share only. |
| `OBSERVABILITY_STACK_ADDRESS` | `10.42.0.10` | Ansible Builder (`observability`, tenant stacks) | The stack host's declared `ipv4_address` on the bridge, without the prefix. Repository-level: provider-owned and the same for every tenant. Management-plane hosts ship telemetry to it; the lab's own hosts ignore it. See [observability](./observability.md#tenant-guests-over-the-management-plane). |

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
| `BUILDER_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Ansible Builder | Private half of the Builder keypair, written `0600` to the runner's default identity path. Only needed once a tenant stack exists: tenant VMs sit on a tailnet the runner is not on, so the Builder hops through the hypervisor to plain `sshd`, which needs a key to trust. `gh secret set BUILDER_SSH_PRIVATE_KEY < ~/.ssh/autolab-builder`. |
| `NAS_SMB_PASSWORD` | random | Ansible Builder (`storage`) | **Environment-level.** Password for `NAS_SMB_USERNAME`. Rendered into a `0600` credentials file on each host that mounts over SMB; never in fstab, the process list, or a log. `gh secret set NAS_SMB_PASSWORD --env qnta`. |
| `PVE_EXPORTER_TOKEN_SECRET` | `xxxxxxxx-xxxx-...` | Ansible Builder | Secret for the Proxmox read-only token. Separate from `PROXMOX_API_TOKEN`, which can create and destroy VMs; this one holds `PVEAuditor` only. Unset disables the exporter rather than shipping it broken. |
| `PBS_PVE_PASSWORD` | `<long random string>` | Ansible Builder (`backup`), Proxmox Node | Password of the `pve@pbs` account the hypervisor backs up with. Set on the PBS host when the account is created; the node authenticates with it. See [backups](./backups.md). |
| `NTFY_TOPIC` | `autolab-pulsar-xxxxxxxxxx` | Ansible Builder | ntfy topic that alerts publish to. It is the **entire** credential — holding it lets anyone read these alerts and publish to them — so it is a secret, not a variable, and carries random entropy rather than a guessable name. Unset means alerts stay in Grafana and are pushed nowhere. |
| `GF_SECURITY_ADMIN_PASSWORD` | a generated password | Ansible Builder | Grafana admin login. Anonymous *viewing* is deliberate, but the admin account can rewrite dashboards, add datasources and change where alerts go — on the default `admin`/`admin` that is handed to anyone on the tailnet. Unset leaves the existing password alone. |
| `PACKER_SSH_PASSWORD` | generated password | Packer Build | Temporary build-only password. Not your SSH key. |
| `TAILNET_DOMAIN` | `xxx-yyy.ts.net` | every workflow that joins the tailnet | Not a credential. Referenced only so the runner masks it: GitHub masks a secret from a job's first log line, a variable never, and a public repository publishes its logs. Unset means logs show the name; nothing else changes. |
| `CLOUDFLARE_API_TOKEN` | `v1.0-...` | 10 - Cloudflare | Custom token: Zone → DNS → Edit and Account → Cloudflare Tunnel → Edit, scoped to the one zone and account. See [ingress](./ingress.md). |
| `INGRESS_TRAEFIK_CLIENT_ID` | `<uuid>` | Ansible Builder (`ingress`) | The Traefik plugin's OIDC client in Pocket ID: one for every hostname the plugin protects (wildcard callback). Unset means nothing behind the plugin has a route. |
| `INGRESS_TRAEFIK_CLIENT_SECRET` | `<random>` | Ansible Builder (`ingress`) | Its secret. Shown once by Pocket ID. |
| `GRAFANA_OIDC_CLIENT_ID` | `<uuid>` | Ansible Builder (`observability`, `ingress`) | Grafana's own OIDC client in Pocket ID. Set: Grafana logs in via Pocket ID, anonymous viewing off, public route on. Unset: tailnet-only as before. |
| `GRAFANA_OIDC_CLIENT_SECRET` | `<random>` | Ansible Builder (`observability`) | Its secret. |
| `INGRESS_ACME_DNS_TOKEN` | `<token>` | Ansible Builder (`ingress`) | A second Cloudflare token: Zone → DNS → Edit on the one zone, nothing else. Lives on horizon for the wildcard certificate's DNS challenge. Unset: the tailnet side stays off. |
| `PROXMOX_OIDC_CLIENT_ID` | `<uuid>` | Proxmox Node, Ansible Builder (`backup`) | One Pocket ID client for PVE and PBS. Set: both offer a Pocket ID realm. |
| `PROXMOX_OIDC_CLIENT_SECRET` | `<random>` | same | Its secret. |
| `PORTAINER_ADMIN_PASSWORD` | a generated password | Ansible Builder (`services`) | Portainer's local admin, created at first start. Unset and Portainer opens its setup page instead, which expires five minutes in. Portainer CE has no OIDC, so this login sits behind the passkey rather than replacing it. |
| `R2_ACCESS_KEY_ID` | `abc123...` | OpenTofu | R2 → Manage API Tokens. Shown once. |
| `R2_SECRET_ACCESS_KEY` | `xyz789...` | OpenTofu | Same. Shown once. |
| `PVE_SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH...` | Packer Build | Required only as the Proxmox bastion key; never reuse it for a VM. |

## Credentials held outside GitHub

Everything above is a GitHub Actions secret or variable. These are not, which
is exactly why they are listed: an audit that reads only the tables above would
miss them, and they still grant access.

| Credential | Held by | Grants | Rotate |
|---|---|---|---|
| Grafana Git Sync token | Grafana's database on the stack host | Fine-grained GitHub PAT, scoped to this repository: Contents read/write, Pull requests read/write, Webhooks read/write, Metadata and Administration read-only | Grafana → Administration → Provisioning. Not `gh secret set`. |
| Grafana admin password | Set from the `GF_SECURITY_ADMIN_PASSWORD` secret, then stored in Grafana | Full control of dashboards, datasources and alert delivery — including where alerts are sent | Change the secret and redeploy; the role runs `grafana cli admin reset-admin-password` |

The Git Sync token is the one worth thinking about. Whoever holds Grafana admin
can read it out or use it, so it turns "access to Grafana" into "write access
to this repository". That is the trade Git Sync asks for, and it is why the
admin password stopped being `admin` before the token existed.

Set an expiry on it. A token that expires silently stops dashboard sync, and
Grafana does not make that loud.

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

## GitHub Environments

| Environment | Workflow | Holds |
|-------------|----------|-------|
| `lab` | Plan, Apply, Destroy, Builder when `environment: lab` | Nothing yet; the provider's own stack falls through to repository-level values |
| `qnta` | Plan, Apply, Destroy, Builder when `environment: qnta` | `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET` from the tenant's tailnet; `NAS_SMB_PASSWORD`; variables `TAILSCALE_VM_TAG`, `NAS_SERVER`, `NAS_SMB_USERNAME` |
| `autolab-plan`, `autolab-apply` | Not targeted | Retained; nothing reads them |

Plan, Apply, Destroy and Builder run their main job under the GitHub
Environment named after the stack. Environment secrets shadow repository
secrets of the same name, which is the whole mechanism for tenancy: the
`qnta` environment carries a *different* `TAILSCALE_VM_OAUTH_*` pair, so the
same workflow enrols VMs on a different tailnet. Typed confirmations and the
`opentofu-state` concurrency guard are unchanged.

## Quick checklist

**Variables**

- [ ] `PROXMOX_HOST`
- [ ] `PROXMOX_LAN_IP` (required for Debian 13 Packer Build)
- [ ] `PROXMOX_PORT` (optional; defaults to `8006`)
- [ ] `PROXMOX_NODE_NAME`
- [ ] `PROXMOX_INSECURE_TLS` = `true`
- [ ] `PROXMOX_PACKER_NETWORK_BRIDGE`
- [ ] `BUILDER_SSH_PUBLIC_KEY` (once a tenant stack exists)
- [ ] `TAILSCALE_VM_TAG` on each tenant environment
- [ ] `NAS_SERVER`, `NAS_SMB_USERNAME` on each environment whose machines mount the NAS
- [ ] `OBSERVABILITY_STACK_ADDRESS` (once a tenant stack exists)
- [ ] `SSH_PUBLIC_KEYS`

**Secrets**

- [ ] `PROXMOX_API_TOKEN`
- [ ] `PACKER_SSH_PASSWORD` (Packer)
- [ ] `PVE_SSH_PRIVATE_KEY` (Packer)
- [ ] `TAILSCALE_OAUTH_CLIENT_ID` + `TAILSCALE_OAUTH_SECRET` — OAuth client scoped `auth_keys` (owning `tag:ci-runner`) **and** `policy_file`
- [ ] `TAILSCALE_OAUTH_SECRET` — required; how the runner authenticates
- [ ] `TAILSCALE_VM_OAUTH_CLIENT_ID`, `TAILSCALE_VM_OAUTH_SECRET` (OpenTofu only)
- [ ] Add the `policy_file` scope to the existing `TAILSCALE_OAUTH_CLIENT_ID` credential — no new secret; see [tailnet policy GitOps](./tailnet-policy-gitops.md)
- [ ] `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (secrets) and `CLOUDFLARE_ACCOUNT_ID` (variable)
- [ ] Ansible Builder still reuses `CLOUDFLARE_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`; see *Open: scope Builder's R2 access to read-only* below

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
