---
tags: [gitops, opentofu, proxmox, vm, lxc]
status: draft
audience: beginner
---

# Step 4 - OpenTofu VM/LXC provisioning

Phase 2A uses OpenTofu to create VM and LXC resources from the stack's `machines` map.

This assumes you already have:

- a Proxmox host reachable through Tailscale or private LAN
- a Proxmox API token
- a VM cloud-init template (built by Packer or created manually — see below)
- a downloaded LXC container template

## VM templates

OpenTofu clones VMs from an existing cloud-init template on Proxmox. You have two options:

### Option A: Build with Packer (recommended)

Packer builds VM templates from an ISO on your running Proxmox host. This is the recommended approach — it's fully automated and reproducible.

See `infra/packer/` for the Packer config and `docs/gitops/setup-checklist.md` for the full setup steps.

### Option B: Create manually (fallback)

If you want to test OpenTofu before setting up Packer, create a template manually:

1. **Download a cloud-init image** — e.g. Debian 13 (Trixie) qcow2:
   ```bash
   wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2
   ```

2. **Create a VM on Proxmox** using the image:
   ```bash
   qm create 9000 --name "debian-13-template" --memory 2048 --net0 virtio,bridge=vmbr0
   qm importdisk 9000 debian-13-generic-amd64.qcow2 local-lvm
   qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
   qm set 9000 --ide2 local-lvm:cloudinit
   qm set 9000 --boot c --bootdisk scsi0
   qm set 9000 --serial0 socket --vga serial0
   ```

3. **Install qemu-guest-agent** inside the VM:
   ```bash
   qm start 9000
   # SSH in or use the Proxmox console, then:
   # apt update && apt install -y qemu-guest-agent
   qm shutdown 9000
   ```

4. **Convert to template**:
   ```bash
   qm template 9000
   ```

Refer to the [Proxmox cloud-init guide](https://pve.proxmox.com/wiki/Cloud-Init_Support) for detailed options.

## LXC `os_type` variable

The `proxmox-compute` module supports an `os_type` variable (default `"debian"`) for LXC type machines instead of using a hardcoded value. Supported values include:

- `debian`
- `ubuntu`
- `alpine`
- `centos`
- `fedora`
- `opensuse`

Set it in your `terraform.tfvars` under the LXC machine entry in the `machines` map to match the downloaded LXC template.

## Local layout

Terramate generates provider and backend configs so each stack directory stays clean:

```text
infra/
  terramate.tm.hcl
  modules/
    proxmox-connection/
    machine-normalization/   # merges defaults; filters provisioning_class
    proxmox-compute/
    cloud-init/
  stacks/lab/
  _base/
  packer/templates/debian-13/   # Packer-built cloud-init template (VM ID 9000)
```

Copy the example variables:

```bash
cp infra/stacks/lab/terraform.tfvars.example infra/stacks/lab/terraform.tfvars
```

Edit the copied file with your own values. Do not commit it.

The CI workflows use the generated `configure-proxmox-connection` action to map schema-driven connection values into the correct secrets and variables before running OpenTofu.

The `terraform.tfvars.example` uses a `machines` map with `for_each`. Each machine
has a `type` (`vm` or `lxc`) and `provisioning_class` (`builder_target` today;
`cluster_os` is reserved for Talos experiments and **blocked at plan time** until
wired). Shared settings come from `network_defaults`, `identity_defaults`,
`tailscale_auth_key`, and `common_tags`.

The `machine-normalization` module merges those defaults per machine. The lab
stack provisions only `builder_target` machines. VMs get cloud-init from the
`cloud-init` module (admin user, SSH keys, qemu-guest-agent, optional Tailscale).

**CI today:** GitHub Actions injects Proxmox/R2 connection settings from secrets
and variables. The `machines` map is **not** injected — it lives in local
`terraform.tfvars` (gitignored). A CI plan with no local tfvars shows **No changes**.
To create a VM, add a machine entry locally and run `tofu apply`, or use GitHub
Apply after you have a tfvars file on the runner (not supported yet).

To add a machine, add a key to `machines` with `type = "vm"` or `type = "lxc"`.
Set `node_name` only when placing on a node other than the stack default.
`proxmox-compute` validates type-specific fields at plan time.

## Local commands

```bash
cd infra
terramate generate
cd stacks/lab
tofu init -backend-config="endpoint=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com"
tofu fmt -recursive
tofu validate
tofu plan
```

Apply through GitHub Actions reconciles whatever is in `var.machines`. With the
default empty map, apply changes nothing. To create VMs today, define machines in
local `terraform.tfvars` and run `tofu apply` locally (or dispatch GitHub Apply
once CI can read your inventory).

The apply workflow uses `scripts/tofu-apply-with-retry.sh`, which delegates retry
behaviour to `scripts/lib/retry.sh`.

## GitHub apply modes

The apply workflow has two modes:

- `fresh`: generate and apply a new plan in the same workflow job.
- `saved-plan`: download and apply a binary plan artifact from a previous plan workflow run.

Use `fresh` as the default. It is simpler and avoids stale-plan issues between separate workflow runs.

Use `saved-plan` only when you need the stricter review pattern:

1. Run `OpenTofu Plan`.
2. Set `upload_binary_plan` to `true`.
3. Review the text plan artifact and job summary.
4. Copy the plan workflow run ID.
5. Run `OpenTofu Apply` with `plan_mode=saved-plan`, the run ID, and the binary artifact name.

The default binary artifact name for the lab environment is:

```text
opentofu-lab-tfplan
```

## VM vs LXC guidance

Use a VM for:

- public-facing workloads
- Docker hosts
- Talos
- Kubernetes nodes
- stronger isolation

Use an unprivileged LXC for:

- lightweight internal services
- simple Linux utilities
- services that do not need Docker-in-LXC complexity

Avoid privileged LXCs unless the guide for that service explains why.

Sources:

- [bpg/proxmox provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Proxmox Linux containers](https://pve.proxmox.com/wiki/Linux_Container)
