---
tags: [gitops, opentofu, proxmox, vm, lxc]
status: draft
audience: beginner
---

# Step 4 - OpenTofu VM/LXC provisioning

Phase 2A uses OpenTofu to create one VM and one LXC from Proxmox.

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

1. **Download a cloud-init image** — e.g. Debian 12 (Bookworm) qcow2:
   ```bash
   wget https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2
   ```

2. **Create a VM on Proxmox** using the image:
   ```bash
   qm create 9000 --name "debian-12-template" --memory 2048 --net0 virtio,bridge=vmbr0
   qm importdisk 9000 debian-12-generic-amd64.qcow2 local-lvm
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
  modules/proxmox-connection/
  modules/proxmox-compute/
  modules/cloud-init/
  stacks/lab/
  _base/
```

Copy the example variables:

```bash
cp infra/stacks/lab/terraform.tfvars.example infra/stacks/lab/terraform.tfvars
```

Edit the copied file with your own values. Do not commit it.

The CI workflows use the generated `configure-proxmox-connection` action to map schema-driven connection values into the correct secrets and variables before running OpenTofu.

The `terraform.tfvars.example` uses a `machines` map variable with `for_each` to declare VMs and LXCs by key name. Shared settings come from four per-concern variables — `network_defaults`, `identity_defaults`, `tailscale_auth_key`, and `common_tags` — that apply to all machines unless overridden per entry. VMs get cloud-init composed per machine by the `cloud-init` module, which takes a hostname and emits a single `#cloud-config` document with base qemu-guest-agent setup plus optional Tailscale enrollment.

The `cloud-init` module owns Tailscale install, join, retry, and logging command composition. The existing `tailscale_auth_key` variable is enough for the default path; module variables also let you tune retry attempts, retry delay, `--accept-routes`, extra `tailscale up` arguments, and the VM log path without editing generated user-data by hand.

To add a machine, add a new key to the `machines` map with `type = "vm"` or `type = "lxc"` plus the type-specific fields. Set `node_name` on a machine only when you want to place it on a Proxmox node other than the stack default. `proxmox-compute` validates the type-specific requirements at plan time: VMs need `template_vm_id`, VMs with cloud-init user-data need `cloud_init_datastore_id`, and LXCs need `template_file_id`.

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

Apply should normally happen through the protected GitHub Actions workflow once the runner is ready.
The apply workflow uses `scripts/tofu-apply-with-retry.sh`, which delegates retry behaviour to `scripts/lib/retry.sh` so retry attempts, exhaustion, and delay behaviour are covered by bats tests.

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
