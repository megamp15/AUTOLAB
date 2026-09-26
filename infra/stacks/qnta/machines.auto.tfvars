# The QNTA tenant. Same hypervisor, same modules, same workflows as the lab —
# and a different tailnet. The runner never joins it: OpenTofu mints join keys
# with the tenant's OAuth client (GitHub Environment `qnta`), cloud-init enrols
# each VM there, and the Builder reaches the VMs over the hypervisor's private
# bridge instead. See docs/gitops/tenants.md and ADR-0006.
tenant = "qnta"

identity_defaults = {
  admin_username = "autolab"
  # The provider's break-glass key. The Builder's own key is appended at plan
  # time from BUILDER_SSH_PUBLIC_KEY; the tenant's people do not need a key
  # here at all, because they arrive over their tailnet with Tailscale SSH.
  ssh_public_keys = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGX8QG/GhqvODd9Shu5VD6+FU3c0JlBFlWi4m/MLDqCz"]
}

network_defaults = {
  network_bridge = "vmbr1"
  vlan_id        = null
}

# `autolab` marks the VM as ours in the Proxmox UI; `tenant-qnta` says whose
# it is, so a Proxmox view or a PromQL selector can group guests by tenant.
common_tags = ["autolab", "tenant-qnta"]

# Addresses are declared, not leased. vmbr1 is the node's own 10.42.0.0/24
# with dnsmasq leasing .100–.200; tenants take .201 upward, last octet equal to
# the VMID so the two can never disagree. The Builder dials these addresses
# through the hypervisor, so a leased one would be unknowable at plan time.
#
# All of it on pve, the gaming PC: 15.5 GB, 4 cores / 8 threads, 1.6 TB thin.
# 13.5 GB is allocated here, which leaves the host its ~2 GB only while the
# old qcicd guests (502–505) stay stopped. Disk is sized ahead because the
# pool is thin: a volume costs what is written, and it grows online but
# never shrinks.
#
# AUTOLAB provisions and hardens these; everything that runs on them is the
# tenant's, from its own repository. Their telemetry goes to qnta-observability
# over the tenant's tailnet, never to the provider's stack.
machines = {
  # Swarm manager: registry, the management services.
  qnta-mgmt = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "qnta-mgmt"
    vm_id                   = 201
    node_name               = "pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 2
    memory_mb               = 3072
    disk_size_gb            = 128
    ipv4_address            = "10.42.0.201/24"
    ipv4_gateway            = "10.42.0.1"
    builder = {
      docker_enabled = true
      # Swarm control plane and overlay, from the bridge only. The management
      # SSH rule from the hypervisor is injected by the stack; it is not listed.
      firewall_rules = [
        { port = 2377, protocol = "tcp", source = "10.42.0.0/24" },
        { port = 7946, protocol = "tcp", source = "10.42.0.0/24" },
        { port = 7946, protocol = "udp", source = "10.42.0.0/24" },
        { port = 4789, protocol = "udp", source = "10.42.0.0/24" },
      ]
      # The tenant's share on the NAS, over SMB: behind the NAT bridge every
      # VM reaches the NAS as the node, so only a credential can scope access.
      # The server comes from NAS_SERVER on the environment; the credential
      # from NAS_SMB_USERNAME / NAS_SMB_PASSWORD there. Nothing site-specific
      # is written here.
      storage = [
        { protocol = "smb", share = "qnta", path = "/mnt/qnta", credential = "nas", directories = ["qnta-mgmt"] },
      ]
    }
  }

  # Swarm worker: the dev environment.
  qnta-dev = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "qnta-dev"
    vm_id                   = 202
    node_name               = "pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 2
    memory_mb               = 2048
    disk_size_gb            = 64
    ipv4_address            = "10.42.0.202/24"
    ipv4_gateway            = "10.42.0.1"
    builder = {
      docker_enabled = true
      firewall_rules = [
        { port = 7946, protocol = "tcp", source = "10.42.0.0/24" },
        { port = 7946, protocol = "udp", source = "10.42.0.0/24" },
        { port = 4789, protocol = "udp", source = "10.42.0.0/24" },
      ]
      storage = [
        { protocol = "smb", share = "qnta", path = "/mnt/qnta", credential = "nas", directories = ["qnta-dev"] },
      ]
    }
  }

  # Swarm worker: staging, rarely used, so the smallest.
  qnta-stg = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "qnta-stg"
    vm_id                   = 203
    node_name               = "pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 1
    memory_mb               = 1536
    disk_size_gb            = 64
    ipv4_address            = "10.42.0.203/24"
    ipv4_gateway            = "10.42.0.1"
    builder = {
      docker_enabled = true
      firewall_rules = [
        { port = 7946, protocol = "tcp", source = "10.42.0.0/24" },
        { port = 7946, protocol = "udp", source = "10.42.0.0/24" },
        { port = 4789, protocol = "udp", source = "10.42.0.0/24" },
      ]
      storage = [
        { protocol = "smb", share = "qnta", path = "/mnt/qnta", credential = "nas", directories = ["qnta-stg"] },
      ]
    }
  }

  # Swarm worker: production.
  qnta-prd = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "qnta-prd"
    vm_id                   = 204
    node_name               = "pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 2
    memory_mb               = 2048
    disk_size_gb            = 128
    ipv4_address            = "10.42.0.204/24"
    ipv4_gateway            = "10.42.0.1"
    builder = {
      docker_enabled = true
      firewall_rules = [
        { port = 7946, protocol = "tcp", source = "10.42.0.0/24" },
        { port = 7946, protocol = "udp", source = "10.42.0.0/24" },
        { port = 4789, protocol = "udp", source = "10.42.0.0/24" },
      ]
      storage = [
        { protocol = "smb", share = "qnta", path = "/mnt/qnta", credential = "nas", directories = ["qnta-prd"] },
      ]
    }
  }

  # The tenant's horizon: tunnel, reverse proxy, sign-in, internal names.
  qnta-network = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "qnta-network"
    vm_id                   = 205
    node_name               = "pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 1
    memory_mb               = 1024
    disk_size_gb            = 32
    ipv4_address            = "10.42.0.205/24"
    ipv4_gateway            = "10.42.0.1"
    builder = {
      docker_enabled = true
    }
  }

  # The tenant's jwst: metrics, logs, dashboards and alerts for its VMs.
  qnta-observability = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "qnta-observability"
    vm_id                   = 206
    node_name               = "pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 2
    memory_mb               = 4096
    disk_size_gb            = 128
    ipv4_address            = "10.42.0.206/24"
    ipv4_gateway            = "10.42.0.1"
    builder = {
      docker_enabled = true
    }
  }
}
