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

# `autolab` marks the VM as ours in the Proxmox UI. `tenant-qnta` is what the
# lab's observability rules key on to leave these guests alone: they report to
# nothing on the provider's tailnet, and an alert that can never clear is worse
# than no alert.
common_tags = ["autolab", "tenant-qnta"]

# Addresses are declared, not leased. vmbr1 is the node's own 10.42.0.0/24
# with dnsmasq leasing .100–.200; tenants take .201 upward, last octet equal to
# the VMID so the two can never disagree. The Builder dials these addresses
# through the hypervisor, so a leased one would be unknowable at plan time.
#
# Sized for the laptop they live on: 15 GB total, jwst holds 8, sputnik 1,
# and the host wants ~1 for itself. mgmt gets more than dev because it will
# carry the registry, tunnel and management services long before the
# application stacks move. The business stacks proper are not meant to run
# here; growing these is an edit once the second node lands — CPU and memory
# cost a reboot, disk grows online but never shrinks, which is why disk alone
# is sized ahead: the pool is thin and a 64 GB volume costs only what is written.
machines = {
  # Swarm manager: registry, tunnel, internal proxy, the management services.
  qnta-mgmt = {
    type                    = "vm"
    provisioning_class      = "builder_target"
    name                    = "qnta-mgmt"
    vm_id                   = 201
    node_name               = "xps-pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 1
    memory_mb               = 3072
    disk_size_gb            = 64
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
      # The agent ships to jwst by tailnet name, and this VM is not on that
      # tailnet. Provider-side monitoring over the bridge is a later change.
      observability = { agent = false }
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
    node_name               = "xps-pve"
    template_vm_id          = 9002
    datastore_id            = "local-lvm"
    cloud_init_datastore_id = "local-lvm"
    cpu_cores               = 1
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
      observability = { agent = false }
      # The tenant's share on the NAS, over SMB: behind the NAT bridge every
      # VM reaches the NAS as the node, so only a credential can scope access.
      # The server comes from NAS_SERVER on the environment; the credential
      # from NAS_SMB_USERNAME / NAS_SMB_PASSWORD there. Nothing site-specific
      # is written here.
      storage = [
        { protocol = "smb", share = "qnta", path = "/mnt/qnta", credential = "nas", directories = ["qnta-dev"] },
      ]
    }
  }
}
