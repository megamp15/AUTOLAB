identity_defaults = {
  admin_username  = "autolab"
  ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGX8QG/GhqvODd9Shu5VD6+FU3c0JlBFlWi4m/MLDqCz"]
}

network_defaults = {
  network_bridge = "vmbr1"
  vlan_id        = null
}

machines = {
  lab_01 = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "lab-01"
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
      # This VM inherits the universal baseline; no inbound service is exposed.
    }
  }

  # Second Builder target. Its immediate job is to prove the baseline is
  # portable: admin-users, the firewall manifest, the inventory generator, and
  # the NFS mount have only ever run against lab-01, so anything that merely
  # happens to fit one host shows up here.
  #
  # Sized beyond lab-01's canary footprint because this is the intended home for
  # the observability stack, and growing CPU or memory later means a reboot
  # while growing the disk is worse. Cheaper to size it once.
  #
  # 8 GB rather than 4: Alloy plus Mimir, Loki and Grafana lands around 3 GB at
  # rest, and a metrics backend that starts swapping stops being able to tell
  # you why anything is slow. Disk stays modest because Mimir and Loki both
  # persist blocks to R2 rather than to local disk.
  lab_02 = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "lab-02"
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
      # Baseline only for now. No inbound service is exposed until something
      # actually listens, and then it is declared here rather than opened by
      # hand on the host.
    }
  }
}
