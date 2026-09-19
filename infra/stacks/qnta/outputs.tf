output "proxmox" {
  description = "Proxmox connection details (non-sensitive)."
  value = {
    node_name    = module.proxmox.node_name
    endpoint     = module.proxmox.endpoint
    insecure_tls = module.proxmox.insecure_tls
  }
}

output "machines" {
  description = "Created compute resource details, keyed by machine name."
  value = {
    for k, m in module.machine : k => {
      name = m.name
      id   = m.vm_id
      type = m.type
      ipv4 = m.requested_ipv4_address
    }
  }
}

output "builder_machines" {
  description = "Non-sensitive Ansible inventory data for Builder-target VMs."
  value = {
    for key, machine in module.machine_inputs.builder_target_vm_machines : key => {
      name = machine.name
      # Provider VMs are dialled by MagicDNS name on the provider's tailnet.
      # Tenant VMs are on a tailnet the runner is not on, so they are dialled
      # by bridge address through the hypervisor — which is itself reached by
      # the same MagicDNS name the Proxmox API uses.
      ansible_host   = var.tenant == null ? machine.name : machine.management_address
      ssh_jump_host  = var.tenant == null ? null : var.proxmox_host
      # The VM's own bridge address when declared, null when leased. A provider
      # service that tenants reach over the bridge — the observability stack
      # today, PBS later — binds to it; nothing else reads it.
      management_address = machine.management_address
      bootstrap_user = machine.admin_username
      builder        = machine.builder
    }
  }
}
