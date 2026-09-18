output "normalized_machines" {
  description = "Machine declarations with Stack defaults merged in."
  value       = local.normalized_machines
}

output "builder_target_machines" {
  description = "Normalized Machines that use the Linux builder-target provisioning path."
  value       = local.builder_target_machines
}

output "builder_target_vm_machines" {
  description = "Normalized VM Machines that need cloud-init user data for the builder-target path."
  value       = local.builder_target_vm_machines

  # A leased address is unknowable at plan time, and the plan is where the
  # Builder inventory comes from. Fail here, before anything is created, rather
  # than with an inventory that names a VM nothing can dial.
  precondition {
    condition = !var.management_plane || alltrue([
      for _, machine in local.builder_target_vm_machines :
      machine.management_address != null && machine.ipv4_gateway != null
    ])
    error_message = "On the management plane every builder_target Machine needs a static ipv4_address (CIDR) and an ipv4_gateway; \"dhcp\" cannot be dialled through the hypervisor."
  }
}

output "cluster_os_machines" {
  description = "Normalized Cluster OS Machines. Reserved for future Talos-style provisioning."
  value       = local.cluster_os_machines
}
