# The home network's edge, on zima-pve (ZimaBoard 2: 16 GB, two 2.5 GbE ports).
# Provider-owned like the lab: the machines enrol on the lab tailnet and the
# Builder reaches them by name. Unlike the lab they sit on vmbr0, the home
# network itself, because the household is who they serve.
#
# Disks: the eMMC (local-lvm) wears with writes and holds Proxmox; the 1 TB
# HDD (hdd) is old but takes writes without wearing. A machine the household
# depends on goes where its disk fails with the node anyway; a write-heavy one
# goes to the HDD, and nightly backups to ark cover it.
identity_defaults = {
  admin_username  = "autolab"
  ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGX8QG/GhqvODd9Shu5VD6+FU3c0JlBFlWi4m/MLDqCz"]
}

network_defaults = {
  network_bridge = "vmbr0"
  vlan_id        = null
}

common_tags = ["autolab", "edge"]

# VMIDs 301 up. Addresses are declared on the home network, outside the
# router's own reservations; .53 for DNS so it reads as what it is.
machines = {
  # DNS with ad blocking for every device at home: Pi-hole, logging each
  # lookup per device. The magnetosphere turns the solar wind aside before it
  # reaches the ground, as this turns ads aside before they reach a device.
  # On the HDD: it writes every query.
  magnetosphere = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "magnetosphere"
    vm_id                   = 301
    node_name               = "zima-pve"
    template_vm_id          = 9000
    datastore_id            = "hdd"
    cloud_init_datastore_id = "hdd"
    cpu_cores               = 1
    memory_mb               = 1024
    disk_size_gb            = 16
    ipv4_address            = "192.168.50.53/24"
    ipv4_gateway            = "192.168.50.1"
    # DNS comes back first after a node restart.
    startup = { order = 1, up_delay = 10 }
    builder = {
      docker_enabled = true
      pihole         = true
      # DNS for the home network. The admin page is tailnet-only (the
      # baseline allows tailscale0), so nothing else is opened.
      firewall_rules = [
        { port = 53, protocol = "udp", source = "192.168.50.0/24" },
        { port = 53, protocol = "tcp", source = "192.168.50.0/24" },
      ]
      observability = {
        ship_to = "jwst"
      }
    }
  }
}
