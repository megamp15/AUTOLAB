# ---------------------------------------------------------------------------
# Debian 12 Packer template-specific variables (hand-maintained)
#
# Connection variables are generated into connection-vars.pkr.hcl.
# ---------------------------------------------------------------------------

# ---- Template identity ----

variable "vm_template_name" {
  type        = string
  default     = "autolab-debian-12-template"
  description = "Name for the VM template created by Packer"
}

variable "vm_id_base" {
  type        = number
  default     = 9000
  description = "Starting VM ID for templates. Each build increments from here."
}

variable "boot_wait" {
  type        = string
  default     = "10s"
  description = "Wait time before sending the boot command sequence."
}

variable "cores" {
  type        = number
  default     = 2
  description = "Number of CPU cores assigned to the build VM."
}

variable "memory" {
  type        = number
  default     = 2048
  description = "Memory in MB assigned to the build VM."
}

variable "disk_size" {
  type        = string
  default     = "8G"
  description = "Disk size for the build VM."
}

variable "network_model" {
  type        = string
  default     = "virtio"
  description = "Network adapter model for the build VM."
}

variable "network_firewall" {
  type        = bool
  default     = false
  description = "Whether to enable the Proxmox firewall on the build VM NIC."
}

variable "ssh_username" {
  type        = string
  default     = "root"
  description = "SSH username used by Packer to connect after installation."
}

variable "ssh_timeout" {
  type        = string
  default     = "20m"
  description = "Timeout for SSH communicator connection attempts."
}

variable "template_description" {
  type        = string
  default     = "Debian 12 cloud-init template — built by Packer"
  description = "Description applied to the resulting Proxmox template."
}

variable "qemu_agent" {
  type        = bool
  default     = true
  description = "Whether to enable the QEMU guest agent on the build VM."
}

variable "scsi_controller" {
  type        = string
  default     = "virtio-scsi-pci"
  description = "SCSI controller model used by the build VM."
}

variable "disk_type" {
  type        = string
  default     = "scsi"
  description = "Disk interface type used by the build VM."
}

variable "disk_format" {
  type        = string
  default     = "raw"
  description = "Disk image format used by the build VM."
}

# ---- Storage ----

variable "storage_pool" {
  type        = string
  default     = "local-lvm"
  description = "Proxmox storage pool for VM disks and cloud-init drive."
}

variable "cloud_init_storage_pool" {
  type        = string
  default     = null
  description = "Separate storage pool for the cloud-init drive. Defaults to var.storage_pool when null."
}

# ---- ISO ----

variable "iso_file" {
  type        = string
  default     = "local:iso/debian-12.13.0-amd64-netinst.iso"
  description = "Proxmox ISO storage path for the installer ISO. Must already be uploaded to the Proxmox host."
}

variable "iso_checksum" {
  type        = string
  default     = ""
  description = "Checksum for the ISO file (e.g. sha256:abcdef...). Empty string skips verification."
}

variable "boot_iso_type" {
  type        = string
  default     = "scsi"
  description = "Device type for the boot ISO. Common values: scsi, ide, sata, virtio."
}

# ---- SSH access for provisioning ----

variable "ssh_password" {
  type        = string
  default     = "packer"
  description = "Temporary installer SSH password used only while Packer provisions the build VM. The account is locked before the VM is converted to a template."
  sensitive   = true
}

variable "ssh_public_keys" {
  type        = list(string)
  default     = []
  description = "Public SSH keys to inject via cloud-init"
}

variable "root_password" {
  type        = string
  default     = "packer"
  description = "Root password set during Packer build. The root account is locked after provisioning — this password is only used during the automated install."
  sensitive   = true
}

# ---- Network ----

variable "network_bridge" {
  type        = string
  default     = "vmbr0"
  description = "Proxmox bridge for the build VM network interface."
}

# ---- Bastion / SSH relay ----

variable "pve_ssh_host" {
  type        = string
  default     = ""
  description = "Proxmox host SSH address for bastion access. Leave empty if not using SSH bastion."
}

variable "pve_ssh_private_key_file" {
  type        = string
  default     = ""
  description = "Path to SSH private key for PVE bastion access. Leave empty if not using SSH bastion."
}
