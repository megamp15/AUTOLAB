# Autolab Infrastructure

This directory uses [Terramate](https://terramate.io) to manage OpenTofu stacks.

Terramate provides:
- **Code generation** — provider and backend configs are generated once, never duplicated
- **Change detection** — only stacks with changed files are planned/applied in CI
- **Stack ordering** — dependencies between stacks are explicit
- **Scalability** — adding a new environment is just a new stack directory

## Layout

```text
infra/
  terramate.tm.hcl          # Terramate project config + global defaults (R2 bucket, etc.)
  modules/                  # Shared OpenTofu modules
    proxmox-connection/     # Proxmox connection validation and derived values
    machine-normalization/  # Merges defaults; filters builder_target vs cluster_os
    proxmox-compute/        # Unified VM and LXC module (type = "vm" | "lxc")
    cloud-init/             # Cloud-init user-data composition (base + optional Tailscale enrollment)
  stacks/
    lab/                    # First homelab environment
      stack.tm.hcl
      main.tf
      variables.tf
      outputs.tf
      terraform.tfvars.example
  _base/
    providers.tm.hcl        # Generates providers.tf for all stacks
    backend.tm.hcl          # Generates versions.tf (backend + required_providers) for all stacks
    connection-variables.tm.hcl # Generates _connection-variables.tf for all stacks
  packer/
    template-catalog.yaml   # Implemented templates + documented experiments
    templates/              # Per-OS Packer modules (e.g. templates/debian-12/)
```

## Prerequisites

- [OpenTofu](https://opentofu.org/) >= 1.9.0
- [Terramate](https://terramate.io/) >= 0.6.0

## First local run

```bash
# Install Terramate (macOS)
brew install terramate

# Generate provider and backend configs
cd infra
terramate generate

# Copy example variables
cp stacks/lab/terraform.tfvars.example stacks/lab/terraform.tfvars

# Set R2 credentials for state backend
export AWS_ACCESS_KEY_ID=<your-r2-access-key-id>
export AWS_SECRET_ACCESS_KEY=<your-r2-secret-access-key>

# Initialize and plan
cd stacks/lab
tofu init -backend-config="endpoint=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com"
tofu fmt -recursive
tofu validate
tofu plan
```

Do not commit `terraform.tfvars`, state files, plan files, or secrets.

The `machines` map in `terraform.tfvars` defines which VMs/LXCs to create. It is
gitignored and not injected by GitHub Actions today — CI plan/apply smoke tests
run with `machines = {}` unless you apply locally.

## Adding a new environment

To add a new environment (e.g. `prod`):

1. Create a new stack directory: `stacks/prod/`
2. Add a `stack.tm.hcl` with a unique ID and name
3. Copy and customize `main.tf`, `variables.tf`, `outputs.tf`, and `terraform.tfvars.example`
4. Run `terramate generate` to create `providers.tf` and `versions.tf`
5. The state key will automatically be `prod/terraform.tfstate`

## Modules

### proxmox-connection

Validates Connection values and exposes derived values such as the normalised
endpoint and web UI URL. The Connection schema (`infra/connection-schema.yaml`)
is the source of truth for fields and generated adapters. The provider block
still reads from `var.proxmox_*` directly (an OpenTofu limitation), so this
module is intentionally validation-only; see ADR-0002.

### machine-normalization

Merges per-machine config with stack defaults (`network_defaults`,
`identity_defaults`, `common_tags`). Partitions machines by `provisioning_class`:

- `builder_target` — cloud-init + Ansible path; passed to `proxmox-compute`
- `cluster_os` — recognized but **not wired**; plan fails with a clear error until Talos support lands

The lab stack (`infra/stacks/lab/main.tf`) calls this module before `cloud-init`
and `proxmox-compute`.

### proxmox-compute

Unified compute module that creates VMs (`type = "vm"`) or LXCs (`type = "lxc"`).
Shared concepts (network, CPU, memory, disk, SSH, IP, tags, started) are defined
once; type-specific fields (template, OS) branch internally. Cloud-init user-data
is composed by the separate `cloud-init` module and passed as `cloud_init_user_data`.
The module fails at plan time when VM or LXC type-specific inputs are missing,
including the cloud-init datastore required for VM user-data snippets.

### cloud-init

Composes cloud-init user-data from a base template (user, SSH keys, qemu-guest-agent)
and optional Tailscale enrollment. The module owns Tailscale install, join, retry,
logging, and extra argument composition so stacks only pass intent. The compute
module calls this module and passes the resulting `user_data` to the VM resource.

## Provider

Autolab uses the `bpg/proxmox` provider because it supports both Proxmox VMs and LXCs and is actively maintained.

Source: <https://registry.terraform.io/providers/bpg/proxmox/latest/docs>
