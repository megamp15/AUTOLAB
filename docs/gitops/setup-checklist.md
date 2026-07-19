---
tags: [gitops, setup, checklist]
status: draft
audience: operator
---

# Phase 2 setup checklist

From "Proxmox is installed and on Tailscale" to working CI pipelines and your first disposable VM.

Complete these in order. Each step links to the relevant guide for details.

## Prerequisites (phase 1 — already done)

- [ ] Proxmox VE installed and reachable at `https://<host>:8006`
- [ ] Networking configured (USB Ethernet, Wi-Fi failover, or LAN)
- [ ] Host packages updated (`apt update && apt upgrade`)
- [ ] Tailscale installed and the host has joined the tailnet
- [ ] Tailscale SSH enabled (`sudo tailscale set --ssh`)

## 1. Tailscale OAuth client for CI

The GitHub runner needs Tailscale OAuth credentials to join the tailnet temporarily during each workflow run.

- [ ] Go to [Tailscale admin console → OAuth clients](https://login.tailscale.com/admin/settings/oauth)
- [ ] Create a new OAuth client with **Custom scopes**
- [ ] Under **Keys**, grant only **Auth Keys → Write**. Leave all other scopes unchecked.
- [ ] Configure the client to create ephemeral nodes tagged with `tag:ci-runner` (or a tag you choose — note it for the ACL step)
- [ ] Save the **Client ID** and **Client Secret** — you will add them as `TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_SECRET` in GitHub

- [ ] Create the `ci-runner` tag in Tailscale. For **Tag owner**, choose your own identity for a personal lab, or `autogroup:admin` for a team-managed lab. Avoid `autogroup:member` for CI tags.

See [02 - Secure GitHub runner](./02-secure-runner.md) for the full runner model.

## 2. Tailscale ACL

The CI runner tag needs permission to reach the Proxmox host on port 8006.

- [ ] Open [Tailscale ACL editor](https://login.tailscale.com/admin/acls)
- [ ] Add an ACL rule allowing the CI runner tag to reach the Proxmox host tag (or specific IP) on port 8006. Example:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci-runner"],
      "dst": ["tag:autolab:8006"]
    }
  ]
}
```

- [ ] Make sure your Proxmox host is tagged (e.g. `tag:autolab`) in the Tailscale admin console under **Machines**

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

## 5. GitHub Environments and secrets

GitHub Environments group secrets. **Required reviewers is an Enterprise-only feature** — not available on Free/Team plans for private repos.

- [ ] Go to your GitHub repo → **Settings → Environments**
- [ ] Create environment `autolab-plan`
- [ ] Create environment `autolab-apply`
- [ ] Leave **Required reviewers** off (Enterprise-only)
- [ ] Add these **Repository Variables** (non-sensitive) at the repository or organization level:

| Variable | Value |
|----------|-------|
| `PROXMOX_HOST` | Your Proxmox Tailscale hostname (e.g. `<proxmox-host>`) |
| `PROXMOX_ENDPOINT` | `https://<tailscale-magicdns>:8006` (e.g. `https://<proxmox-tailnet-host>:8006`) |
| `PROXMOX_NODE_NAME` | Your Proxmox node name (e.g. `pve`) |
| `PROXMOX_INSECURE_TLS` | Optional; use `true` for Proxmox's default self-signed certificate |
| `SSH_PUBLIC_KEYS` | SSH public keys for Packer template build (comma-separated) |
| `PROXMOX_STORAGE_POOL` | Packer: storage pool for template disks (e.g. `local-lvm`) |
| `PROXMOX_NETWORK_BRIDGE` | Packer: network bridge (e.g. `vmbr0`) |
| `PACKER_ISO_FILE` | Packer: ISO path (e.g. `local:iso/debian-12.13.0-amd64-netinst.iso`) |

- [ ] Add these **secrets** (repository or environment level):

| Secret | Value |
|--------|-------|
| `TAILSCALE_OAUTH_CLIENT_ID` | Tailscale OAuth client ID from step 1 |
| `TAILSCALE_OAUTH_SECRET` | Tailscale OAuth client secret from step 1 |
| `PROXMOX_API_TOKEN` | Full Proxmox API token string from step 3, e.g. `gitops@pve!opentofu=SECRET` |
| `PACKER_SSH_PASSWORD` | Generated password for Packer Build (temporary, build-only) |
| `R2_ACCOUNT_ID` | Cloudflare account ID from step 4 |
| `R2_ACCESS_KEY_ID` | R2 access key ID from step 4 |
| `R2_SECRET_ACCESS_KEY` | R2 secret access key from step 4 |
| `TAILSCALE_VM_AUTHKEY` | Optional for first plan smoke test; needed when VMs should join Tailscale |

If you already added these as **repository secrets**, the workflows can still read them. Keep going for a personal-lab smoke test, but prefer copying them into `autolab-plan` and `autolab-apply` environment secrets before doing real apply runs.

- [ ] (Enterprise only) Add **required reviewers** to `autolab-apply` if you want manual approval before apply runs

See [GitHub Secrets & Variables Reference](./github-secrets-variables-reference.md) for per-field "where to get it" details, and [06 - GitHub Environments](./06-github-environments.md) for environment setup.

## 6. Proxmox VM template

OpenTofu clones VMs from an existing template. You have two options:

### Option A: Build with Packer (recommended)

Packer builds templates from an ISO on your running Proxmox host — no manual steps needed beyond uploading the ISO.

- [ ] Upload a Debian 12 netinst ISO to Proxmox ISO storage (via the UI or `wget` on the host)
- [ ] Copy the Packer variables example:

```bash
cp infra/packer/templates/debian-12/debian-12.pkrvars.example infra/packer/templates/debian-12/debian-12.pkrvars.hcl
```

- [ ] Edit `infra/packer/templates/debian-12/debian-12.pkrvars.hcl` with your Proxmox endpoint, API token, node name, and SSH public keys
- [ ] Run Packer from a machine that can reach Proxmox over Tailscale:

```bash
cd infra/packer/templates/debian-12
packer init .
packer validate -var-file=debian-12.pkrvars.hcl .
packer build -var-file=debian-12.pkrvars.hcl .
```

- [ ] Note the template VM ID (default 9000) — it must match `template_vm_id` in your `terraform.tfvars`. The default comes from `debian-12` in `infra/packer/template-catalog.yaml`.

### Option B: Create manually (quick start fallback)

If you want to test OpenTofu before setting up Packer:

- [ ] Download a cloud-init image on the Proxmox host:

```bash
wget https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2
```

- [ ] Create a VM from the image:

```bash
qm create 9000 --name "debian-12-template" --memory 2048 --net0 virtio,bridge=vmbr0
qm importdisk 9000 debian-12-generic-amd64.qcow2 local-lvm
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
- [ ] Download the template you want (e.g. `Debian 12 Standard`)
- [ ] Note the template file ID (e.g. `local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst`) — it must match `template_file_id` in your `terraform.tfvars`

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
  - `proxmox_endpoint` — your Proxmox API URL (Tailscale hostname)
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
- [ ] Manually trigger **OpenTofu Plan** (workflow dispatch) and verify the pipeline initializes, reads R2 backend credentials, and receives the Proxmox/Tailscale connection settings
- [ ] Treat the first plan as a smoke test. With no committed `terraform.tfvars`, `var.machines` defaults to `{}`, so a clean **No changes** result is expected until you add VM/LXC entries locally.
- [ ] To actually create a VM today, copy `terraform.tfvars.example` to a local `terraform.tfvars`, add your machine entry, then run `tofu plan` and `tofu apply` locally. CI injects Proxmox/R2 connection settings from GitHub secrets and variables, but not the `machines` map.

---

## Phase 2B steps (Packer — ready to use)

The Packer scaffold is in `infra/packer/`. To build templates:

- [ ] Upload a Debian netinst ISO to Proxmox ISO storage
- [ ] Copy `infra/packer/templates/debian-12/debian-12.pkrvars.example` to `infra/packer/templates/debian-12/debian-12.pkrvars.hcl` and fill in values
- [ ] Run `packer init`, `packer validate`, `packer build` from a machine that can reach Proxmox over Tailscale
- [ ] Or run the existing **Packer Build** GitHub Actions workflow after adding the Packer CI variables/secrets from `infra/packer/README.md`

## Phase 2C manual steps (Ansible — not yet)

These will be needed when Ansible hardening roles are added:

- [ ] Create a non-root admin user on each VM/LXC
- [ ] Create a `gitops` deploy user for Ansible
- [ ] Configure SSH key access for the `gitops` user
- [ ] (These will be automated by Ansible once the roles are written)
