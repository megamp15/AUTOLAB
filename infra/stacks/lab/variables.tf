# ---- Proxmox connection ----
# Connection variables are AUTO-GENERATED from infra/connection-schema.yaml
# by scripts/generate-connection-adapters.sh into _connection-variables.tf.
# Do not declare them here — they are managed by Terramate code generation.

# ---- Network defaults ----

variable "network_defaults" {
  description = "Shared network defaults merged into every machine."
  type = object({
    network_bridge = string
    vlan_id        = number
  })
  default = {
    network_bridge = "vmbr0"
    vlan_id        = null
  }
}

# ---- Identity defaults ----

variable "identity_defaults" {
  description = "Shared identity defaults merged into every machine."
  type = object({
    admin_username  = string
    ssh_public_keys = list(string)
  })
  default = {
    admin_username  = "autolab"
    ssh_public_keys = []
  }
}

# ---- Tailscale ----

variable "tailscale_auth_key" {
  description = "Tailscale auth key for VMs to join the tailnet on first boot. Use an ephemeral reusable key tagged for VMs. Empty string skips Tailscale enrollment (base cloud-init still applied)."
  type        = string
  default     = ""
  sensitive   = true
}

# ---- Tags ----

variable "common_tags" {
  description = "Tags applied to every machine."
  type        = list(string)
  default     = ["autolab", "gitops", "phase-2a"]
}

# ---- Machines ----

variable "machines" {
  description = "Map of compute resources to create. Each entry has a type (vm or lxc) and type-specific config. Shared defaults come from var.network_defaults, var.identity_defaults, var.common_tags, and var.tailscale_auth_key (via the cloud-init module)."
  type = map(object({
    type = string
    # Identity
    name      = string
    vm_id     = number
    node_name = optional(string, null)
    # VM-specific (ignored for LXC)
    template_vm_id          = optional(number, null)
    template_node_name      = optional(string, null)
    cloud_init_datastore_id = optional(string, null)
    admin_username          = optional(string, null)
    # LXC-specific (ignored for VM)
    template_file_id = optional(string, null)
    os_type          = optional(string, "debian")
    # Shared compute
    datastore_id = string
    cpu_cores    = number
    memory_mb    = number
    disk_size_gb = number
    ipv4_address = optional(string, "dhcp")
    ipv4_gateway = optional(string, null)
    started      = optional(bool, true)
  }))
  default = {}
}
