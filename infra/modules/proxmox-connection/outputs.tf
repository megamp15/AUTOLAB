output "endpoint" {
  description = "Proxmox API endpoint URL (normalised, no trailing slash)."
  value       = local.endpoint_normalised
}

output "api_token" {
  description = "Proxmox API token."
  value       = var.api_token
  sensitive   = true
}

output "insecure_tls" {
  description = "Whether to skip TLS verification for Proxmox."
  value       = var.insecure_tls
}

output "node_name" {
  description = "Default Proxmox node name."
  value       = var.node_name
}

output "web_ui_url" {
  description = "Proxmox web UI URL (derived from endpoint)."
  value       = local.web_ui_url
}