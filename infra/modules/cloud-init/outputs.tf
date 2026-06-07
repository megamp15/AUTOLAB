output "user_data" {
  description = "Composed cloud-init user-data string for VM initialization."
  value       = local.user_data
  sensitive   = true
}
