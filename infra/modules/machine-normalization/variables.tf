# ---------------------------------------------------------------------------
# machine-normalization — normalizes Stack Machine declarations.
#
# This module owns default merging and type partitioning so Stacks can stay
# wiring-focused while proxmox-compute receives fully-shaped inputs.
# ---------------------------------------------------------------------------

variable "machines" {
  description = "Raw Machine declarations from the Stack."
  type = map(object({
    type               = string
    provisioning_class = optional(string, "builder_target")

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
    tags         = optional(list(string), [])
    started      = optional(bool, true)
  }))
  default = {}
  validation {
    condition = alltrue([
      for _, machine in var.machines :
      contains(["builder_target", "cluster_os"], machine.provisioning_class)
    ])
    error_message = "Each Machine provisioning_class must be \"builder_target\" or \"cluster_os\"."
  }
}

variable "default_node_name" {
  description = "Fallback Proxmox node name for Machines that do not set node_name."
  type        = string
}

variable "network_defaults" {
  description = "Shared network defaults merged into every Machine."
  type = object({
    network_bridge = string
    vlan_id        = number
  })
}

variable "identity_defaults" {
  description = "Shared identity defaults merged into every Machine."
  type = object({
    admin_username  = string
    ssh_public_keys = list(string)
  })
}

variable "common_tags" {
  description = "Tags applied to every Machine before adding the Machine type tag."
  type        = list(string)
}
