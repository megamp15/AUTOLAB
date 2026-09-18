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
    builder = optional(object({
      enabled = optional(bool, true)
      firewall_rules = optional(list(object({
        port     = number
        protocol = optional(string, "tcp")
        source   = optional(string, "any")
      })), [])
      docker_enabled = optional(bool, false)
      # NAS shares this machine mounts, applied by the storage playbook. `server`
      # may be omitted to take the Stack's nas_server, so the machines map never
      # carries an address that belongs to the site rather than the machine.
      storage = optional(list(object({
        protocol    = optional(string, "nfs")
        server      = optional(string, null)
        share       = string
        path        = string
        credential  = optional(string, null)
        directories = optional(list(string), [])
        options     = optional(string, null)
        mode        = optional(string, null)
      })), [])
      # Must mirror the builder object in each stack's variables.tf. A field
      # missing here is silently dropped as the map passes through, so the
      # policy reaches neither builder_machines nor the Ansible inventory.
      observability = optional(object({
        stack = optional(bool, false)
        # Defaults true: a machine is monitored unless it says otherwise.
        # Setting false skips the agent install *and* excludes the guest from
        # the "Agent is not reporting" rule, which would otherwise fire forever
        # for a machine behaving exactly as designed.
        agent = optional(bool, true)
      }), {})
    }), {})
  }))
  default = {}
  validation {
    condition = alltrue([
      for _, machine in var.machines :
      contains(["builder_target", "cluster_os"], machine.provisioning_class)
    ])
    error_message = "Each Machine provisioning_class must be \"builder_target\" or \"cluster_os\"."
  }
  validation {
    condition = alltrue([
      for _, machine in var.machines :
      machine.provisioning_class != "builder_target" || machine.type == "vm"
    ])
    error_message = "Each builder_target Machine must have type = \"vm\"."
  }
  validation {
    condition = alltrue(flatten([
      for _, machine in var.machines : [
        for rule in machine.builder.firewall_rules :
        rule.port >= 1 && rule.port <= 65535 && contains(["tcp", "udp"], rule.protocol)
      ]
    ]))
    error_message = "Each Builder firewall rule requires a port from 1 through 65535 and protocol tcp or udp."
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

variable "management_plane" {
  description = <<-EOT
    Reach Builder targets over the hypervisor's private bridge instead of the
    provider's tailnet. A tenant Stack enrols its VMs on the tenant's tailnet,
    which the provider's CI runner is not on, so the Builder hops through the
    hypervisor and addresses each VM by its bridge address. That address must
    therefore be declared, not leased: every builder_target Machine needs a
    static ipv4_address and an ipv4_gateway.
  EOT
  type        = bool
  default     = false
}

variable "nas_server" {
  description = <<-EOT
    Default NAS address for storage entries that do not name a server. Comes
    from the GitHub Environment (NAS_SERVER) rather than the machines map, so
    the site's address lives in one place and a change there does not touch
    the code. Over the tailnet this is a MagicDNS name; over the LAN, the
    address the router reserves for the NAS.
  EOT
  type        = string
  default     = null
}
