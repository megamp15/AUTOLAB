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
}
