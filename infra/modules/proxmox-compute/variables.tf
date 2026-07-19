# ---------------------------------------------------------------------------
# proxmox-compute — unified VM and LXC module
#
# Shared concepts (network, CPU, memory, disk, SSH, IP, tags, started) are
# defined once.  Type-specific fields (template, cloud-init, OS) branch on
# var.type.
# ---------------------------------------------------------------------------

variable "type" {
  description = "Compute type: vm or lxc."
  type        = string
  validation {
    condition     = contains(["vm", "lxc"], var.type)
    error_message = "Type must be \"vm\" or \"lxc\"."
  }
}

variable "name" {
  description = "Resource name (VM name or LXC hostname)."
  type        = string
}

variable "node_name" {
  description = "Target Proxmox node name."
  type        = string
}

variable "vm_id" {
  description = "VM or container ID."
  type        = number
}

# ---- Shared fields ----

variable "datastore_id" {
  description = "Datastore for the primary disk. For VMs this is the clone target datastore."
  type        = string
}

variable "network_bridge" {
  description = "Proxmox bridge to attach the network device to."
  type        = string
}

variable "vlan_id" {
  description = "Optional VLAN ID. Leave null if you are not using VLANs."
  type        = number
  default     = null
}

variable "cpu_cores" {
  description = "CPU cores."
  type        = number
}

variable "memory_mb" {
  description = "Dedicated memory in MB."
  type        = number
}

variable "disk_size_gb" {
  description = "Primary disk size in GB."
  type        = number
}

variable "ssh_public_keys" {
  description = "Public SSH keys injected at provisioning time. Never put private keys here."
  type        = list(string)
  default     = []
}

variable "ipv4_address" {
  description = "IPv4 address in CIDR notation or \"dhcp\"."
  type        = string
  default     = "dhcp"
}

variable "ipv4_gateway" {
  description = "IPv4 gateway when using a static address."
  type        = string
  default     = null
}

variable "tags" {
  description = "Proxmox tags."
  type        = list(string)
  default     = []
}

variable "started" {
  description = "Start the resource after creation."
  type        = bool
  default     = true
}

# ---- VM-specific fields ----

variable "template_vm_id" {
  description = "Existing Proxmox template VM ID to clone (VM only)."
  type        = number
  default     = null
}

variable "template_node_name" {
  description = "Node where the source template exists. Defaults to var.node_name (VM only)."
  type        = string
  default     = null
}

variable "cloud_init_datastore_id" {
  description = "Datastore for the cloud-init drive (VM only)."
  type        = string
  default     = null
}

variable "admin_username" {
  description = "Initial non-root admin user created by cloud-init (VM only)."
  type        = string
  default     = "autolab"
}

variable "cloud_init_user_data" {
  description = "Pre-composed cloud-init user-data string. Typically from the cloud-init module."
  type        = string
  default     = ""
  sensitive   = true
}

# ---- LXC-specific fields ----

variable "template_file_id" {
  description = "Proxmox template file ID, e.g. local:vztmpl/debian-standard.tar.zst (LXC only)."
  type        = string
  default     = null
}

variable "os_type" {
  description = "Operating system type for the container. Common values: debian, ubuntu, alpine, centos, fedora, archlinux (LXC only)."
  type        = string
  default     = "debian"
}
