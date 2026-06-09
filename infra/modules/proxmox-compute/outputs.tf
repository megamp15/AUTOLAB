output "name" {
  description = "Resource name (VM name or LXC hostname)."
  value       = var.name
}

output "vm_id" {
  description = "VM or container ID."
  value       = var.type == "vm" ? proxmox_virtual_environment_vm.vm[0].vm_id : proxmox_virtual_environment_container.lxc[0].vm_id
}

output "type" {
  description = "Compute type that was provisioned."
  value       = var.type
}

output "requested_ipv4_address" {
  description = "IPv4 address requested during initialization."
  value       = var.ipv4_address
}
