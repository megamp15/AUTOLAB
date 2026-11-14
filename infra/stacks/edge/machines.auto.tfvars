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

  # The lab's applications: Forgejo (the code, mirrors of upstream and our
  # forks) and the self-hosted apps built from it — a travel log, recipes,
  # flights, bookmarks, finances. What the lab runs for itself stays on jwst
  # (Dockhand, the registry, the editor); what people use lives here.
  #
  # Here, not on jwst, for two reasons. RAM: the apps and the builds from
  # source come to ~3.5 GB steady and spike past that, on a host that already
  # OOM-killed Prometheus's neighbours sixteen times. Wire: xps-pve is Wi-Fi
  # only, and these mount the NAS with `hard` NFS, which hangs a VM when the
  # link stalls; zima-pve is wired.
  #
  # State is on the NAS (/mnt/apps): uploads, repositories, source checkouts and
  # the nightly database dumps. Live Postgres data stays on this VM's disk,
  # because a database on NFS v3 is a corruption story waiting for a link
  # blip; the dumps and PBS are its copies. HDD for that reason: it writes.
  #
  # 302: 301 is magnetosphere. DHCP: the home router reserves it; the NAS rule
  # is by tailnet name, which follows the machine.
  nebula = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "nebula"
    vm_id                   = 302
    node_name               = "zima-pve"
    template_vm_id          = 9000
    datastore_id            = "hdd"
    cloud_init_datastore_id = "hdd"
    cpu_cores               = 4
    memory_mb               = 8192
    disk_size_gb            = 80
    ipv4_address            = "dhcp"
    builder = {
      docker_enabled = true
      # What it runs. The names are the catalog's (playbooks/group_vars/all.yml)
      # and must equal autolab_remote_services.nebula there; a test fails the
      # build if they drift.
      services = ["adventurelog", "forgejo", "tandoor", "airtrail", "linkace", "sure"]
      # Temporarily share the existing export; isolate PBS into its own share later.
      storage = [
        { protocol = "nfs", server = "singularity", share = "/volume1/autolab", path = "/mnt/apps", directories = ["backups"], mode = "0755" },
      ]
      observability = {
        ship_to = "jwst"
      }
    }
  }
}
