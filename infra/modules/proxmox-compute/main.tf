# ---------------------------------------------------------------------------
# proxmox-compute — unified VM and LXC resource
#
# Creates a proxmox_virtual_environment_vm when type = "vm" or a
# proxmox_virtual_environment_container when type = "lxc".
# ---------------------------------------------------------------------------

# ---- VM (type = "vm") ----

resource "proxmox_virtual_environment_file" "cloud_init" {
  count = var.type == "vm" && var.cloud_init_enabled ? 1 : 0

  # Keep user-data as a separate snippets file because Proxmox initialization references it by file ID.
  content_type = "snippets"
  datastore_id = var.cloud_init_snippet_datastore_id
  node_name    = var.node_name

  source_raw {
    data      = var.cloud_init_user_data
    file_name = "${var.name}-cloud-init.yaml"
  }

  lifecycle {
    precondition {
      condition     = !var.cloud_init_enabled || (var.cloud_init_datastore_id != null && var.cloud_init_snippet_datastore_id != null)
      error_message = "cloud_init_datastore_id and cloud_init_snippet_datastore_id must be set when cloud_init_enabled is true (type = \"vm\")."
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

    # Readiness is established by Tailscale/SSH checks after cloud-init, not Proxmox guest-agent IP discovery.
    wait_for_ip {
      disabled = true
    }
  }

  cpu {
    cores = var.cpu_cores
  }

  memory {
    dedicated = var.memory_mb
    # floating == dedicated: the balloon device exists but never balloons.
    # Without it Proxmox writes balloon=0, has no way to ask the guest what it
    # uses, and reports the host-side size of the whole qemu process instead —
    # a flat "102%" on every VM, in the UI and in pve_memory_usage_bytes on
    # the dashboards. The guest agent does not help; only the balloon driver
    # reports guest memory. Adding the device is a reboot; it cannot hot-plug.
    floating = var.memory_mb
  }

  disk {
    # Full clones and this explicit disk keep each VM's managed boot disk independent.
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

    # Declared address, declared resolvers. The node's dnsmasq hands 1.1.1.1
    # to leased VMs; a static VM asks nobody and inherits the hypervisor's
    # resolv.conf, which is not a contract. Only for static VMs — adding a
    # block to a leased VM's cloud-init would replace it.
    dynamic "dns" {
      for_each = var.ipv4_address == "dhcp" ? [] : [1]
      content {
        servers = var.dns_servers
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
# LXC intentionally omits VM-only fields; Builder support remains deferred until its reachable-host contract is met.

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
