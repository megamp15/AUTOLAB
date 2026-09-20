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
    cpu_cores               = 1
    memory_mb               = 1024
    disk_size_gb            = 20
    ipv4_address            = "dhcp"
    builder = {
      # Disposable probe. Inherits the universal baseline and exposes nothing;
      # its job is to be rebuilt often enough that the baseline stays honest.
    }
  }


  # Backup server. Proxmox Backup Server as packages on the same Debian
  # template as every other VM, not the PBS ISO: the ISO has no cloud-init,
  # so it would enrol on nothing, get no gitops user and sit outside the
  # baseline. An ark carries everything through the flood — see naming.md.
  #
  # The chunk store is on singularity over NFS, under the autolab share the
  # Builder hosts already mount; the local disk only holds the OS and the
  # cache a later S3 datastore needs. Declared address on the bridge, .11 by
  # the convention jwst set: the hypervisor dials it there for backups, off
  # the tailnet, and the PBS UI comes over tailscale0 which the baseline
  # already allows. Two vCPUs and 2 GB is small for PBS and enough for four
  # guests; the node has 15 GB and this is the last of it.
  ark = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "ark"
    vm_id                   = 104
    node_name               = "xps-pve"
    template_vm_id          = 9000
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 2
    memory_mb               = 2048
    disk_size_gb            = 32
    ipv4_address            = "10.42.0.11/24"
    ipv4_gateway            = "10.42.0.1"
    builder = {
      backup = {
        server = true
      }
      # 8007 is the PBS API. Only the node needs it over the bridge; the
      # UI is reached over the tailnet.
      firewall_rules = [
        { port = 8007, protocol = "tcp", source = "10.42.0.1/32" },
      ]
      # The datastore lives in a directory of its own on the share. The NAS
      # export rule for this host's tailnet address must exist before the
      # backup playbook runs — see docs/gitops/backups.md.
      storage = [
        { protocol = "nfs", server = "singularity", share = "/volume1/autolab", path = "/mnt/autolab", directories = ["ark"], mode = "0750" },
      ]
    }
  }

  # Observability host. Named for what it does, not where it sits — see the
  # naming scheme in docs/gitops/naming.md.
  #
  # Sized beyond lab-01's canary footprint because this is the intended home for
  # the observability stack, and growing CPU or memory later means a reboot
  # while growing the disk is worse. Cheaper to size it once.
  #
  # 6 GB: Alloy plus Prometheus, Loki and Grafana lands around 3 GB at rest,
  # and a metrics backend that starts swapping stops being able to tell you
  # why anything is slow. Was 8 until the tenant VMs needed the room on a
  # 15 GB node; the working set never approached it.
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
    memory_mb               = 6144
    disk_size_gb            = 40
    # Declared, not leased: tenant guests ship telemetry to this address over
    # the bridge, and a lease is unknowable to a stack that cannot see this
    # one. Provider services take .2–.99, below dnsmasq's .100–.200 lease
    # range; tenants take .201 upward. ark, when it lands, is .11.
    ipv4_address = "10.42.0.10/24"
    ipv4_gateway = "10.42.0.1"
    builder = {
      docker_enabled = true
      observability = {
        stack = true
      }
      # Grafana is reached over the tailnet, which the baseline already allows
      # on tailscale0. Nothing is opened to the LAN.
      #
      # The bridge gets two ingest-only ports, answered by Alloy rather than
      # by Prometheus or Loki: a tenant guest can push its metrics and journal
      # here and cannot query anyone's. Alloy is a host process, so these are
      # real ufw rules — unlike the Docker-published tailnet ports.
      firewall_rules = [
        { port = 9009, protocol = "tcp", source = "10.42.0.0/24" },
        { port = 3101, protocol = "tcp", source = "10.42.0.0/24" },
      ]
    }
  }
}
