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

variable "cloud_init_snippet_datastore_id" {
  description = "Datastore for cloud-init snippet files uploaded for VMs."
  type        = string
  default     = "local"
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

# ---- Tenancy ----

variable "tenant" {
  description = <<-EOT
    Who the Machines in this Stack belong to. null means the provider itself:
    VMs enrol on the provider's tailnet and the Builder reaches them by name.
    A tenant name means the VMs enrol on that tenant's tailnet (its OAuth
    client and tag come from the GitHub Environment of the same name) and the
    Builder reaches them over the management plane through the hypervisor.
  EOT
  type        = string
  default     = null
}

variable "tailscale_vm_tag" {
  description = <<-EOT
    Tag the VMs enrol under, and the only tag the destroy-time cleanup may
    delete. Set per GitHub Environment (TAILSCALE_VM_TAG) so a tenant Stack
    names its own tag on its own tailnet.
  EOT
  type        = string
  default     = "tag:autolab-vm"
  validation {
    condition     = can(regex("^tag:[a-z0-9-]+$", var.tailscale_vm_tag))
    error_message = "tailscale_vm_tag must look like tag:name (lowercase letters, digits, hyphens)."
  }
}

variable "builder_ssh_public_key" {
  description = <<-EOT
    Public half of the Builder's SSH keypair (BUILDER_SSH_PUBLIC_KEY). Placed
    on the break-glass user of tenant VMs by cloud-init so the very first
    Builder run can get in over the management plane, where Tailscale SSH
    cannot vouch for the runner. Ignored for the provider's own Stack, whose
    VMs are reached over the tailnet — and whose cloud-init must not change,
    because a changed snippet replaces the VM.
  EOT
  type        = string
  default     = ""
}

variable "nas_server" {
  description = "Default NAS address for storage entries that omit `server` (NAS_SERVER on the GitHub Environment)."
  type        = string
  default     = null
}

# ---- Tags ----

variable "common_tags" {
  description = "Tags applied to every machine."
  type        = list(string)
  default     = ["autolab", "gitops", "phase-2a"]
}

# ---- Machines ----

variable "machines" {
  description = "Map of compute resources to create. Each entry has a type (vm or lxc), a provisioning_class (builder_target or cluster_os), and type-specific config. Shared defaults come from var.network_defaults, var.identity_defaults, and var.common_tags. Builder target VMs receive per-machine Tailscale enrollment keys."
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
    # Builder policy is consumed after provisioning by Ansible, not Proxmox.
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
      # Every Builder host runs the observability agent; `stack` marks the one
      # host that also runs the backends it reports to.
      observability = optional(object({
        stack = optional(bool, false)
        # Defaults true: a machine is monitored unless it says otherwise.
        # Setting false skips the agent install *and* excludes the guest from
        # the "Agent is not reporting" rule, which would otherwise fire forever
        # for a machine behaving exactly as designed.
        agent = optional(bool, true)
      }), {})
      # The machine that runs Proxmox Backup Server. Marks it the way
      # observability.stack marks the metrics host: the backup playbook finds
      # it by this flag, nothing else reads it.
      backup = optional(object({
        server = optional(bool, false)
      }), {})
    }), {})
  }))
  default = {}
  validation {
    condition = alltrue([
      for _, machine in var.machines :
      contains(["builder_target", "cluster_os"], machine.provisioning_class)
    ])
    error_message = "Each machine provisioning_class must be \"builder_target\" or \"cluster_os\"."
  }
  validation {
    condition = alltrue([
      for _, machine in var.machines :
      machine.provisioning_class != "cluster_os"
    ])
    error_message = "Cluster OS machines are recognized as disposable experiments, but the Talos/OpenTofu implementation is not wired yet. Keep them in docs or comments until the cluster_os path is implemented."
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
