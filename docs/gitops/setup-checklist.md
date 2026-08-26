---
tags: [gitops, setup, checklist]
status: draft
audience: operator
---

# Phase 2 setup checklist

From "Proxmox is installed and on Tailscale" to working CI pipelines and the
Packer/template lifecycle.

Complete these in order. Each step links to the relevant guide for details.

## Prerequisites (phase 1 — already done)

- [ ] Proxmox VE installed and reachable at `https://<host>:8006`
- [ ] Networking configured (USB Ethernet, Wi-Fi failover, or LAN)
- [ ] Host packages updated (`apt update && apt upgrade`)
- [ ] Tailscale installed and the host has joined the tailnet
- [ ] Builder VM Tailscale SSH host feature is enabled by cloud-init after enrollment

## 1. Tailscale GitHub OIDC/WIF for CI

The GitHub runner uses GitHub OIDC/WIF to obtain short-lived tailnet access;
do not create or store a long-lived OAuth client secret for Builder CI.

- [ ] Configure the tailnet trust integration and GitHub OIDC provider for the repository and workflow claims
- [ ] Bind the workflow identity to the exact `tag:ci-runner` tag
- [ ] Restrict tag assignment to the tailnet administrator or approved provisioning authority

- [ ] Create `tag:ci-runner`; set `tagOwners` to the tailnet administrator or approved WIF principal, never a broad member group

See [02 - Secure GitHub runner](./02-secure-runner.md) for the full runner model.

## 2. Tailscale ACL and SSH policy

The CI runner tag needs permission to reach Proxmox on port 8006 and Builder
VMs over Tailscale SSH. Tag the CI runner and every Builder VM explicitly. The
SSH policy must grant access for `autolab` during canary bootstrap and for
`gitops` after the first Builder run creates that account.

- [ ] Open [Tailscale ACL editor](https://login.tailscale.com/admin/acls)
- [ ] Add an ACL rule allowing the CI runner tag to reach the Proxmox host tag (or specific IP) on port 8006. Example:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci-runner"],
      "dst": ["<proxmox-host>:8006"]
    }
  ]
}
```

- [ ] Add the Builder grant separately with `dst: ["tag:autolab-vm"]` and `ip: ["tcp:22"]`
- [ ] Add a separate SSH accept rule for `tag:ci-runner` to `tag:autolab-vm`, with
  `users: ["autolab", "gitops"]` only; never allow `root`

- [ ] Record the Proxmox host's MagicDNS name or address for the `8006` grant
- [ ] Tag the CI runner as `tag:ci-runner` and each Builder VM as `tag:autolab-vm`
- [ ] Add tailnet grants from `tag:ci-runner` to Proxmox and `tag:autolab-vm`
- [ ] Add SSH accept rules limited to `autolab` for bootstrap and `gitops` afterward; never grant `root`
- [ ] Before replacing a Builder VM, retire its existing `tag:autolab-vm` device first so its stable MagicDNS target is not suffixed or stale
- [ ] After retirement or destruction, revoke/expire its short-lived enrollment key; Terraform does not automatically clean up Tailscale devices

See [02 - Secure GitHub runner](./02-secure-runner.md) for the full runner model.

## 3. Proxmox API token

OpenTofu and Packer need a Proxmox API token to create resources.

- [ ] In the Proxmox web UI, go to **Datacenter → Permissions → API Tokens**
- [ ] Create a dedicated user (e.g. `gitops@pve`) or use an existing user
- [ ] Create an API token for that user (e.g. `gitops@pve!opentofu`)
- [ ] Grant the token permissions on the node, resource pool, and storage you want to manage. Minimum for the lab:
  - `PVEVMAdmin` on the target node
  - `Datastore.AllocateSpace` and `Datastore.AllocateTemplate` on the storage
  - `VM.Audit`, `VM.Allocate`, `VM.Clone`, `VM.Config.Disk`, `VM.Config.CPU`, `VM.Config.Memory`, `VM.Config.Network`, `VM.Config.Options`, `VM.Monitor`, `VM.Power.Mgmt`
- [ ] Save the full token string (`USER@REALM!TOKENID=SECRET`) — you will add it as `PROXMOX_API_TOKEN` in GitHub

See [03 - Proxmox API token](./03-proxmox-api-token.md) for details.

## 4. Cloudflare R2 state backend

OpenTofu state is stored in Cloudflare R2 (S3-compatible, free tier).

- [ ] Sign up or log in to [Cloudflare](https://dash.cloudflare.com/)
- [ ] Navigate to **R2** and create a bucket named `autolab-opentofu-state`
- [ ] Go to **Manage R2 API Tokens** and create a token with **Object Read & Write** permissions
- [ ] Save the **Access Key ID** and **Secret Access Key** — you will add them as `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` in GitHub
- [ ] Copy your **Cloudflare Account ID** from the R2 dashboard URL (the `YOUR_ACCOUNT_ID` part in `https://dash.cloudflare.com/YOUR_ACCOUNT_ID/r2/...`)
- [ ] Add the account ID as `R2_ACCOUNT_ID` in GitHub Environment secrets

See [05 - R2 state backend](./05-r2-state-backend.md) for the full guide.

## 5. GitHub repository secrets

The current Plan, Apply, and Destroy workflows read repository-level secrets
and use typed confirmations; they do not assign a GitHub Environment.
Environments are optional future protection. **Required reviewers is an
Enterprise-only feature** — not available on Free/Team plans for private repos.

- [ ] Optionally create `autolab-plan` and `autolab-apply` for future environment-scoped protection
- [ ] Add these **Repository Variables** (non-sensitive) at the repository or organization level:

| Variable | Value |
|----------|-------|
| `PROXMOX_HOST` | Your Proxmox Tailscale hostname (e.g. `<proxmox-host>`) |
| `PROXMOX_PORT` | Optional API HTTPS port; defaults to `8006` |
| `PROXMOX_NODE_NAME` | Your Proxmox node name (e.g. `pve`) |
| `PROXMOX_INSECURE_TLS` | Optional; use `true` for Proxmox's default self-signed certificate |
| `PROXMOX_PACKER_NETWORK_BRIDGE` | Required bridge for the temporary Packer VM (e.g. `vmbr1`); no `vmbr0` fallback |
| `SSH_PUBLIC_KEYS` | SSH public keys for Packer template build (comma-separated) |
| `TAILSCALE_OIDC_AUDIENCE` | Non-secret GitHub OIDC/WIF audience for the existing Tailscale client ID |

- [ ] Add these **secrets** (repository or environment level):

| Secret | Value |
|--------|-------|
| `PROXMOX_API_TOKEN` | Full Proxmox API token string from step 3, e.g. `gitops@pve!opentofu=SECRET` |
| `PACKER_SSH_PASSWORD` | Generated password for Packer Build (temporary, build-only) |
| `PVE_SSH_PRIVATE_KEY` | Private SSH key for the required Proxmox bastion connection only; never a Builder VM key |
| `TAILSCALE_OAUTH_CLIENT_ID` | Existing Tailscale client ID used with GitHub OIDC/WIF; no Builder OAuth secret |
| `TAILSCALE_VM_OAUTH_CLIENT_ID` | Dedicated Tailscale OAuth client ID for VM enrollment AND destroy-time device cleanup (Plan/Apply/Destroy). Create it in the admin console with **only** the `devices:core:read_write` scope — not the CI-runner client, never with `auth_keys` scope. |
| `TAILSCALE_VM_OAUTH_SECRET` | Secret for the same client (`tskey-client-secret-...`, shown once). See `docs/gitops/tailscale-device-lifecycle.md`. |
| `R2_ACCOUNT_ID` | Cloudflare account ID from step 4 |
| `R2_ACCESS_KEY_ID` | R2 access key ID from step 4 |
| `R2_SECRET_ACCESS_KEY` | R2 secret access key from step 4 |

Repository-level secrets are read directly by the workflows.

For initial Builder canary validation, reuse `R2_ACCOUNT_ID`,
`R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` with the existing state bucket.
Builder-specific credentials are not an immediate prerequisite.

> **TODO after successful canary validation:** add
> `BUILDER_R2_ACCESS_KEY_ID` and `BUILDER_R2_SECRET_ACCESS_KEY` to the Builder
> Environment with R2 Object Read-only scope on the existing state bucket.

- [ ] (Enterprise only) Add **required reviewers** if you later assign a workflow to `autolab-apply`

See [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md) for per-field "where to get it" details, and [06 - GitHub Environments](./06-github-environments.md) for environment setup.

For the complete GitHub UI entry steps, PVE SSH bastion key setup, and local
SSH diagnosis, see [Manual GitHub UI Packer setup](./github-ui-packer-setup.md).

## 6. Proxmox VM template

OpenTofu clones VMs from an existing template. You have two options:

### Option A: Build with Packer (recommended)

Packer asks Proxmox to download the pinned ISO URL directly into the `local`
storage pool. The URL and verified checksum are owned by the selected catalog
entry; there is no manual ISO upload step or ISO repository variable.

- [ ] Copy the Packer variables example:

```bash
cp infra/packer/templates/debian-13/debian-13.pkrvars.example infra/packer/templates/debian-13/debian-13.pkrvars.hcl
```

- [ ] Edit `infra/packer/templates/debian-13/debian-13.pkrvars.hcl` with your Proxmox endpoint, API token, node name, and SSH public keys
- [ ] For local validation, run `eval "$(bash scripts/resolve-packer-template.sh debian-13)"` and `export PKR_VAR_iso_url PKR_VAR_iso_checksum` from the repository root so the catalog supplies the required ISO variables
- [ ] Run Packer from a machine that can reach Proxmox over Tailscale:

```bash
cd infra/packer/templates/debian-13
packer init .
packer validate -var-file=debian-13.pkrvars.hcl .
packer build -var-file=debian-13.pkrvars.hcl .
```

- [ ] Note the template VM ID (default 9000) — it must match `template_vm_id` in your `terraform.tfvars`. The default comes from `debian-13` in `infra/packer/template-catalog.yaml`.

Current Packer defaults are API port `8006` (optional `PROXMOX_PORT` override),
bridge `vmbr0`, and VM disk/cloud-init storage `local-lvm`. The catalog, not
GitHub UI, owns the selected ISO URL and checksum.

Keep the previous ISO/template available deliberately for rollback; this setup
never auto-deletes old ISO files. Before switching VM definitions to a new
template, build and test that new template separately.

### Option B: Create manually (quick start fallback)

If you want to test OpenTofu before setting up Packer:

- [ ] Download a cloud-init image on the Proxmox host:

```bash
wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2
```

- [ ] Create a VM from the image:

```bash
qm create 9000 --name "debian-13-template" --memory 2048 --net0 virtio,bridge=vmbr0
qm importdisk 9000 debian-13-generic-amd64.qcow2 local-lvm
qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
qm set 9000 --ide2 local-lvm:cloudinit
qm set 9000 --boot c --bootdisk scsi0
qm set 9000 --serial0 socket --vga serial0
```

- [ ] Start the VM, install qemu-guest-agent, then shut it down:

```bash
qm start 9000
# SSH in or use the Proxmox console:
# apt update && apt install -y qemu-guest-agent
qm shutdown 9000
```

- [ ] Convert to template:

```bash
qm template 9000
```

- [ ] Note the template VM ID (9000) — it must match `template_vm_id` in your `terraform.tfvars`

See [04 - OpenTofu VM/LXC provisioning](./04-opentofu-vm-lxc.md) for details.

## 7. Proxmox LXC template (download)

LXC templates are downloaded directly in Proxmox — no manual VM creation needed.

- [ ] In the Proxmox UI, go to your node → **local** storage → **CT Templates**
- [ ] Download the template you want (e.g. `Debian 13 Standard`)
- [ ] Note the template file ID (e.g. `local:vztmpl/debian-standard.tar.zst`) — it must match `template_file_id` in your `terraform.tfvars`

## 8. Local OpenTofu configuration

- [ ] Install Terramate (macOS):

```bash
brew install terramate
```

- [ ] Copy the example variables file:

```bash
cp infra/stacks/lab/terraform.tfvars.example infra/stacks/lab/terraform.tfvars
```

- [ ] Edit `terraform.tfvars` with your actual values:
  - `proxmox_host` — your Proxmox hostname or IP
  - `proxmox_port` — optional API port; defaults to `8006`
  - `proxmox_api_token` — the token from step 3
  - `proxmox_node_name` — your Proxmox node name
  - `identity_defaults.ssh_public_keys` — your public key(s) for cloned VMs
  - `example_vm.template_vm_id` — the template ID from step 6
  - `example_lxc.template_file_id` — the template file ID from step 7

- [ ] Set R2 credentials as environment variables for local use:

```bash
export AWS_ACCESS_KEY_ID=<your-r2-access-key-id>
export AWS_SECRET_ACCESS_KEY=<your-r2-secret-access-key>
```

- [ ] Generate Terramate configs and initialize OpenTofu:

```bash
cd infra
terramate generate
cd stacks/lab
tofu init -backend-config="endpoint=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com"
```

- [ ] Verify the plan:

```bash
tofu plan
```

## 9. Verify GitHub Actions

- [ ] Push to `main` (or your working branch) on GitHub
- [ ] Check that the **OpenTofu CI** workflow runs on push (format + validate)
- [ ] Manually trigger **03 - OpenTofu Plan** (workflow dispatch) and verify the pipeline initializes, reads R2 backend credentials, and receives the Proxmox/Tailscale connection settings
- [ ] Treat the first plan as a pipeline smoke test. The CI path reads the committed `infra/stacks/lab/machines.auto.tfvars` desired state, including the running `lab-01` VM; review the resulting changes rather than expecting an empty machine inventory.
- [ ] Do not run local `tofu apply` or `tofu destroy` for normal operation. Use the GitHub Actions workflows for apply and destroy; `machines.auto.tfvars` is the committed GitOps-managed inventory.

---

## Phase 2B steps (Packer — ready to use)

The Packer scaffold is in `infra/packer/`. To build templates:

- [ ] Copy `infra/packer/templates/debian-13/debian-13.pkrvars.example` to `infra/packer/templates/debian-13/debian-13.pkrvars.hcl` and fill in values
- [ ] Run `packer init`, `packer validate`, `packer build` from a machine that can reach Proxmox over Tailscale
- [ ] Or run the existing **02 - Packer Build** GitHub Actions workflow after adding the Packer CI variables/secrets from `infra/packer/README.md`; choose `debian-13` or the separately implemented `ubuntu-26.04` template

## Phase 2C manual steps (Ansible)

Before the first Builder run:

- [ ] Confirm the CI runner can use Tailscale SSH to the canary as `autolab` under the bootstrap SSH policy.
- [ ] Run workflow **05 - Ansible Builder** once as `autolab`; it creates the `gitops` user before SSH policy changes.
- [ ] Update/confirm the SSH policy for `gitops`, then run the regular Builder path as `gitops` and confirm the second run reports no changes.
- [ ] Run optional Docker only after the baseline is healthy.
- [ ] For each service VM, declare only its required `builder.firewall_rules` in `machines.auto.tfvars`.
- [ ] Confirm the stack has at least one enabled Builder Machine before a Builder run; the run stops during inventory preparation, before Ansible, when none are enabled.
- [ ] Treat malformed `builder_machines` output as an inventory error and correct the stack output before rerunning the Builder.
- [ ] Use the persistent canary for the first Builder bootstrap and transport check; this checklist records the procedure, not an executed canary run.
