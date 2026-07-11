output "normalized_machines" {
  description = "Machine declarations with Stack defaults merged in."
  value       = local.normalized_machines
}

output "vm_machines" {
  description = "Normalized Machines that need VM-only cloud-init user data."
  value       = local.vm_machines
}
