identity_defaults = {
  admin_username  = "autolab"
  ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGX8QG/GhqvODd9Shu5VD6+FU3c0JlBFlWi4m/MLDqCz"]
}

network_defaults = {
  network_bridge = "vmbr1"
  vlan_id        = null
}

machines = {
  sputnik = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "sputnik"
    vm_id                   = 100
    node_name               = "xps-pve"
    template_vm_id          = 9000
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 2
    memory_mb               = 2048
    disk_size_gb            = 20
    ipv4_address            = "dhcp"
    builder = {
      # Disposable probe. Inherits the universal baseline and exposes nothing;
      # its job is to be rebuilt often enough that the baseline stays honest.
    }
  }

  # Observability host. Named for what it does, not where it sits — see the
  # naming scheme in docs/gitops/naming.md.
  #
  # Sized beyond lab-01's canary footprint because this is the intended home for
  # the observability stack, and growing CPU or memory later means a reboot
  # while growing the disk is worse. Cheaper to size it once.
  #
  # 8 GB rather than 4: Alloy plus Mimir, Loki and Grafana lands around 3 GB at
  # rest, and a metrics backend that starts swapping stops being able to tell
  # you why anything is slow. Disk stays modest because Mimir and Loki both
  # persist blocks to R2 rather than to local disk.
  jwst = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "jwst"
    vm_id                   = 101
    node_name               = "xps-pve"
    template_vm_id          = 9000
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 4
    memory_mb               = 8192
    disk_size_gb            = 40
    ipv4_address            = "dhcp"
    builder = {
      docker_enabled = true
      observability = {
        stack = true
      }
      # Grafana is reached over the tailnet, which the baseline already allows
      # on tailscale0. Nothing is opened to the LAN.
    }
  }

  # Temporary. Exists to exercise two things nothing else has: the guest-down
  # alert, which needs a VM that Proxmox is told to start on boot and then finds
  # stopped, and the destroy-time Tailscale device cleanup, which has never run
  # against a real machine.
  #
  # Removed by deleting this block and applying again. That destroys only this
  # machine and fires its own cleanup provisioner, where running the destroy
  # workflow would take the whole stack.
  probe = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "probe"
    vm_id                   = 102
    node_name               = "xps-pve"
    template_vm_id          = 9000
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 1
    memory_mb               = 1024
    disk_size_gb            = 10
    ipv4_address            = "dhcp"
    builder = {
      # Nothing. The baseline alone is the point.
    }
  }
}
