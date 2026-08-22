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
      name           = machine.name
      ansible_host   = machine.name
      bootstrap_user = machine.admin_username
      builder        = machine.builder
    }
  }
}
