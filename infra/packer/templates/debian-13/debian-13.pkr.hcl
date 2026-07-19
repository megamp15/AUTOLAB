# ---------------------------------------------------------------------------
# Debian 13 cloud-init VM template
#
# Builds a Proxmox VM template from the Debian 13 netinst ISO using the
# proxmox-iso builder (bpg/proxmox plugin).
#
# How it works:
#   1. Boots the Debian netinst ISO with an automated preseed config
#   2. Installs a minimal Debian 13 system
#   3. Installs qemu-guest-agent and ensures cloud-init is present
#   4. Converts the VM to a Proxmox template
#
# All site-specific values (storage pool, ISO, SSH password, etc.) are
# Packer variables with sensible defaults. Override them via .pkrvars.hcl
# files, PKR_VAR_ environment variables, or GitHub vars/secrets in CI.
# ---------------------------------------------------------------------------

packer {
  required_plugins {
    proxmox = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/proxmox"
    }
  }
}

locals {
  proxmox_api_token_parts    = split("=", var.proxmox_api_token)
  proxmox_api_token_username = local.proxmox_api_token_parts[0]
  proxmox_api_token_secret   = local.proxmox_api_token_parts[1]
}

# ---- Source: proxmox-iso builder ----

source "proxmox-iso" "debian-13" {
  # Connection (mirrors proxmox-connection module schema)
  proxmox_url              = var.proxmox_endpoint
  username                 = local.proxmox_api_token_username
  token                    = local.proxmox_api_token_secret
  node                     = var.proxmox_node_name
  insecure_skip_tls_verify = var.proxmox_insecure_tls

  # VM identity
  vm_id   = var.vm_id_base
  vm_name = var.vm_template_name
  tags    = "autolab;template"

  # OS / ISO
  boot_iso {
    type             = var.boot_iso_type
    iso_url          = var.iso_url
    iso_checksum     = var.iso_checksum
    iso_storage_pool = "local"
    iso_download_pve = true
    unmount          = true
  }

  # Preseed config — served via Packer's HTTP server during install
  http_content = {
    "/preseed.cfg" = templatefile("${path.root}/debian-13-preseed.cfg.tpl", {
      ssh_keys      = var.ssh_public_keys
      root_password = var.root_password
    })
  }

  # Kernel boot params: point the installer at our preseed
  boot_wait = var.boot_wait
  boot_command = [
    "<esc><wait>",
    "auto url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg",
    " netcfg/choose_interface=auto",
    " priority=critical",
    "<enter>"
  ]

  # Hardware
  cores      = var.cores
  memory     = var.memory
  qemu_agent = var.qemu_agent

  # Disk / Storage
  scsi_controller = var.scsi_controller
  disks {
    disk_size    = var.disk_size
    storage_pool = var.storage_pool
    type         = var.disk_type
    format       = var.disk_format
  }

  # Network
  network_adapters {
    bridge   = var.network_bridge
    model    = var.network_model
    firewall = var.network_firewall
  }

  # Cloud-init — enabled on the resulting template so cloned VMs get
  # network config, SSH keys, and user data from Proxmox.
  cloud_init              = true
  cloud_init_storage_pool = coalesce(var.cloud_init_storage_pool, var.storage_pool)

  # SSH access for provisioning
  communicator = "ssh"
  ssh_username = var.ssh_username
  ssh_password = var.ssh_password # temporary build-only password; account is locked before templating
  ssh_timeout  = var.ssh_timeout

  # Convert to template after provisioning
  template_description = var.template_description
  template_name        = var.vm_template_name
}

# ---- Provisioners ----

build {
  name    = "autolab-debian-13"
  sources = ["source.proxmox-iso.debian-13"]

  # Install qemu-guest-agent (required for VM management / IP reporting)
  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "apt-get update -qq",
      "apt-get install -y -qq qemu-guest-agent",
      "systemctl enable qemu-guest-agent",
      # Clean up package cache to reduce template disk usage
      "apt-get clean",
      "rm -rf /var/cache/apt/archives/*",
      "rm -rf /tmp/*"
    ]
  }

  # Clean cloud-init data so cloned VMs get fresh cloud-init on first boot
  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "sudo cloud-init clean --machine-id --seed --logs",
      "sudo rm -rf /var/lib/cloud/instances/*",
      "sudo rm -rf /var/lib/cloud/data/*",
      "sudo rm -rf /var/lib/cloud/sem/*",
      "sudo truncate -s 0 /etc/machine-id",
      "sudo rm -f /var/lib/dbus/machine-id",
      "sudo ln -s /etc/machine-id /var/lib/dbus/machine-id",
      "sudo rm -f /etc/netplan/50-cloud-init.yaml"
    ]
  }

  # Lock the packer user — it was only needed during the build
  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "sudo usermod -L packer",
      "sudo usermod -p '!' packer",
      "sudo usermod -s /usr/sbin/nologin packer"
    ]
  }

  # Lock root account — only needed during automated install
  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "sudo usermod -L root",
      "sudo usermod -p '!' root"
    ]
  }

  # Zero out free space for better compression when cloning
  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "dd if=/dev/zero of=/zero bs=1M || true",
      "rm -f /zero",
      "sync"
    ]
  }
}
