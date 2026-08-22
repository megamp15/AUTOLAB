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
and `common_tags`. Builder target VMs receive a per-VM, single-use Tailscale
enrollment key from the Tailscale provider; the LXC path does not create one.

The `machine-normalization` module merges those defaults per machine. The lab
stack provisions only `builder_target` machines. VMs get cloud-init from the
`cloud-init` module (admin user, qemu-guest-agent, Tailscale enrollment, and
the post-enrollment Tailscale SSH host feature). Builder VMs use
`tag:autolab-vm`; CI reaches them as `tag:ci-runner` under the tailnet grants
and SSH policy.

**Current desired state:** `infra/stacks/lab/machines.auto.tfvars` is committed
and defines the running `lab-01` cloud-init-capable VM Builder target. GitHub
Actions injects Proxmox/R2 connection settings from secrets and variables and
plans this inventory. LXC Builder targets are deferred until they meet the same
reachable-host contract. Do not use local `tofu apply` or `tofu destroy` for
normal operation; use the GitHub Actions workflows.

To add a Builder target, add a key to `machines` with `type = "vm"`. LXC Builder targets are deferred.
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

The local commands above are validation and planning only. Normal apply and
destroy operations belong to protected GitHub Actions; the committed
`machines.auto.tfvars` is the GitOps-managed inventory.

Plan and Apply remain separate workflows. Apply creates a fresh plan, then applies
that binary plan once and preserves the apply log, plan text artifact, and job
summary. A binary plan is never retried: if an apply retry is needed, create a
fresh plan first and apply the new plan.

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
