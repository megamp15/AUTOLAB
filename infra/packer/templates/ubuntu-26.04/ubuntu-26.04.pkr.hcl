# ---------------------------------------------------------------------------
# Ubuntu 26.04 cloud-init VM template
#
# Builds a Proxmox VM template from the Ubuntu live-server ISO using
# Subiquity autoinstall and a temporary NoCloud seed CD.
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

source "proxmox-iso" "ubuntu-26.04" {
  proxmox_url              = var.proxmox_endpoint
  username                 = local.proxmox_api_token_username
  token                    = local.proxmox_api_token_secret
  node                     = var.proxmox_node_name
  insecure_skip_tls_verify = var.proxmox_insecure_tls

  vm_id   = var.vm_id
  vm_name = var.vm_template_name
  tags    = "autolab;template"

  boot_iso {
    type             = var.boot_iso_type
    iso_url          = var.iso_url
    iso_checksum     = var.iso_checksum
    iso_storage_pool = "local"
    iso_download_pve = true
    unmount          = true
  }

  additional_iso_files {
    cd_content = {
      "user-data" = templatefile("${path.root}/user-data", {
        ssh_keys             = var.ssh_public_keys
        packer_password_hash = var.packer_password_hash
      })
      "meta-data" = templatefile("${path.root}/meta-data", {})
    }
    cd_label          = "cidata"
    iso_storage_pool  = "local"
    unmount           = true
  }

  boot_wait = var.boot_wait
  boot_command = [
    "<esc><wait>",
    "c<wait>",
    "linux /casper/vmlinuz --- autoinstall<enter><wait>",
    "initrd /casper/initrd<enter><wait>",
    "boot<enter>"
  ]

  cores      = var.cores
  memory     = var.memory
  qemu_agent = var.qemu_agent

  scsi_controller = var.scsi_controller
  disks {
    disk_size    = var.disk_size
    storage_pool = var.storage_pool
    type         = var.disk_type
    format       = var.disk_format
  }

  network_adapters {
    bridge   = var.network_bridge
    model    = var.network_model
    firewall = var.network_firewall
  }

  cloud_init              = true
  cloud_init_storage_pool = coalesce(var.cloud_init_storage_pool, var.storage_pool)

  communicator = "ssh"
  ssh_username = var.ssh_username
  ssh_password = var.ssh_password
  ssh_timeout  = var.ssh_timeout
  ssh_bastion_host             = var.ssh_bastion_host
  ssh_bastion_username         = var.ssh_bastion_username
  ssh_bastion_private_key_file = var.ssh_bastion_private_key_file

  template_description = var.template_description
  template_name        = var.vm_template_name
}

build {
  name    = "autolab-ubuntu-26.04"
  sources = ["source.proxmox-iso.ubuntu-26.04"]

  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "sudo -n apt-get update -qq",
      "sudo -n apt-get install -y -qq qemu-guest-agent cloud-init openssh-server",
      "sudo -n systemctl enable qemu-guest-agent",
      "sudo -n apt-get clean",
      "sudo -n rm -rf /var/cache/apt/archives/*",
      "sudo -n rm -rf /tmp/*"
    ]
  }

  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "sudo -n cloud-init clean --machine-id --seed --logs",
      "sudo -n rm -rf /var/lib/cloud/instances/* /var/lib/cloud/data/* /var/lib/cloud/sem/*",
      "sudo -n truncate -s 0 /etc/machine-id",
      "sudo -n rm -f /var/lib/dbus/machine-id",
      "sudo -n ln -s /etc/machine-id /var/lib/dbus/machine-id"
    ]
  }

  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "sudo -n dd if=/dev/zero of=/zero bs=1M || true",
      "sudo -n rm -f /zero",
      "sudo -n sync"
    ]
  }

  provisioner "shell" {
    execute_command = "{{ .Vars }} bash -e '{{ .Path }}'"
    inline = [
      "sudo -n bash -c 'rm -rf /home/packer/.ssh; printf \"%s\\n\" \"PasswordAuthentication no\" \"KbdInteractiveAuthentication no\" \"ChallengeResponseAuthentication no\" | tee /etc/ssh/sshd_config.d/99-autolab-template.conf >/dev/null; systemctl reload ssh; rm -f /etc/sudoers.d/90-autolab-packer; usermod -L packer; usermod -s /usr/sbin/nologin packer; usermod -L root'"
    ]
  }
}
