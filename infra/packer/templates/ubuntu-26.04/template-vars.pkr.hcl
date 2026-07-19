# ---------------------------------------------------------------------------
# Ubuntu 26.04 Packer template-specific variables (hand-maintained)
#
# Connection variables are generated into connection-vars.pkr.hcl.
# ISO variables are required and supplied by the catalog resolver.
# ---------------------------------------------------------------------------

variable "vm_template_name" {
  type        = string
  description = "Catalog-derived name for the VM template created by Packer"
}

variable "vm_id" {
  type        = number
  description = "Catalog-derived fixed VM ID for this template release"
}

variable "boot_wait" {
  type        = string
  default     = "10s"
  description = "Wait time before sending the boot command sequence"
}

variable "cores" {
  type        = number
  default     = 2
  description = "Number of CPU cores assigned to the build VM"
}

variable "memory" {
  type        = number
  default     = 2048
  description = "Memory in MB assigned to the build VM"
}

variable "disk_size" {
  type        = string
  default     = "8G"
  description = "Disk size for the build VM"
}

variable "network_model" {
  type        = string
  default     = "virtio"
  description = "Network adapter model for the build VM"
}

variable "network_firewall" {
  type        = bool
  default     = false
  description = "Whether to enable the Proxmox firewall on the build VM NIC"
}

variable "ssh_username" {
  type        = string
  default     = "packer"
  description = "Non-root SSH username used by Packer during provisioning"
}

variable "ssh_password" {
  type        = string
  sensitive   = true
  description = "Required temporary installer password for the packer account"
}

variable "packer_password_hash" {
  type        = string
  sensitive   = true
  description = "Required SHA-512 crypt hash derived from the CI SSH password"
}

variable "ssh_timeout" {
  type        = string
  default     = "20m"
  description = "Timeout for SSH communicator connection attempts"
}

variable "template_description" {
  type        = string
  default     = "Ubuntu 26.04 cloud-init template — built by Packer"
  description = "Description applied to the resulting Proxmox template"
}

variable "qemu_agent" {
  type        = bool
  default     = true
  description = "Whether to enable the QEMU guest agent on the build VM"
}

variable "scsi_controller" {
  type        = string
  default     = "virtio-scsi-pci"
  description = "SCSI controller model used by the build VM"
}

variable "disk_type" {
  type        = string
  default     = "scsi"
  description = "Disk interface type used by the build VM"
}

variable "disk_format" {
  type        = string
  default     = "raw"
  description = "Disk image format used by the build VM"
}

variable "storage_pool" {
  type        = string
  default     = "local-lvm"
  description = "Proxmox storage pool for VM disks and cloud-init drive"
}

variable "cloud_init_storage_pool" {
  type        = string
  default     = null
  description = "Separate storage pool for the cloud-init drive"
}

variable "iso_url" {
  type        = string
  description = "Pinned URL supplied by the catalog resolver"
}

variable "iso_checksum" {
  type        = string
  description = "Required SHA-256 checksum supplied by the catalog resolver"
}

variable "boot_iso_type" {
  type        = string
  default     = "scsi"
  description = "Device type for the boot ISO"
}

variable "ssh_public_keys" {
  type        = list(string)
  default     = []
  description = "Public SSH keys to inject into the packer account"
}

variable "network_bridge" {
  type        = string
  default     = "vmbr0"
  description = "Proxmox bridge for the build VM network interface"
}

variable "ssh_bastion_host" {
  type        = string
  description = "Proxmox SSH bastion host supplied by the hosted CI setup"
}

variable "ssh_bastion_username" {
  type        = string
  description = "SSH username for the Proxmox bastion"
}

variable "ssh_bastion_private_key_file" {
  type        = string
  description = "Path to the SSH private key for the Proxmox bastion"
}
