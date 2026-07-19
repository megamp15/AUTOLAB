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
}

output "cluster_os_machines" {
  description = "Normalized Cluster OS Machines. Reserved for future Talos-style provisioning."
  value       = local.cluster_os_machines
}
