# ---------------------------------------------------------------------------
# proxmox-compute — unified VM and LXC resource
#
# Creates a proxmox_virtual_environment_vm when type = "vm" or a
# proxmox_virtual_environment_container when type = "lxc".
# ---------------------------------------------------------------------------

# ---- VM (type = "vm") ----

resource "proxmox_virtual_environment_file" "cloud_init" {
  count = var.type == "vm" && var.cloud_init_user_data != "" ? 1 : 0

  content_type = "snippets"
  datastore_id = var.cloud_init_datastore_id
  node_name    = var.node_name

  source_raw {
    data      = var.cloud_init_user_data
    file_name = "${var.name}-cloud-init.yaml"
  }

  lifecycle {
    precondition {
      condition     = var.cloud_init_user_data == "" || var.cloud_init_datastore_id != null
      error_message = "cloud_init_datastore_id must be set when cloud_init_user_data is provided (type = \"vm\")."
    }
  }
}

resource "proxmox_virtual_environment_vm" "vm" {
  count = var.type == "vm" ? 1 : 0

  name        = var.name
  description = "Managed by Autolab OpenTofu"
  node_name   = var.node_name
  vm_id       = var.vm_id
  tags        = var.tags
  started     = var.started

  lifecycle {
    precondition {
      condition     = var.template_vm_id != null
      error_message = "template_vm_id is required when type = \"vm\"."
    }
  }

  clone {
    vm_id        = var.template_vm_id
    node_name    = coalesce(var.template_node_name, var.node_name)
    datastore_id = var.datastore_id
    full         = true
  }

  agent {
    enabled = true
  }

  cpu {
    cores = var.cpu_cores
  }

  memory {
    dedicated = var.memory_mb
  }

  disk {
    datastore_id = var.datastore_id
    interface    = "scsi0"
    size         = var.disk_size_gb
  }

  network_device {
    bridge  = var.network_bridge
    vlan_id = var.vlan_id
  }

  initialization {
    datastore_id = var.cloud_init_datastore_id

    ip_config {
      ipv4 {
        address = var.ipv4_address
        gateway = var.ipv4_gateway
      }
    }

    user_account {
      username = var.admin_username
      keys     = var.ssh_public_keys
    }

    user_data_file_id = try(proxmox_virtual_environment_file.cloud_init[0].id, null)
  }
}

# ---- LXC (type = "lxc") ----

resource "proxmox_virtual_environment_container" "lxc" {
  count = var.type == "lxc" ? 1 : 0

  description   = "Managed by Autolab OpenTofu"
  node_name     = var.node_name
  vm_id         = var.vm_id
  tags          = var.tags
  unprivileged  = true
  started       = var.started
  start_on_boot = true

  lifecycle {
    precondition {
      condition     = var.template_file_id != null
      error_message = "template_file_id is required when type = \"lxc\"."
    }
  }

  cpu {
    cores = var.cpu_cores
  }

  memory {
    dedicated = var.memory_mb
  }

  disk {
    datastore_id = var.datastore_id
    size         = var.disk_size_gb
  }

  initialization {
    hostname = var.name

    ip_config {
      ipv4 {
        address = var.ipv4_address
        gateway = var.ipv4_gateway
      }
    }

    user_account {
      keys = var.ssh_public_keys
    }
  }

  network_interface {
    name    = "veth0"
    bridge  = var.network_bridge
    vlan_id = var.vlan_id
  }

  operating_system {
    template_file_id = var.template_file_id
    type             = var.os_type
  }
}
