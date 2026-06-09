// TERRAMATE: GENERATED AUTOMATICALLY DO NOT EDIT

variable "proxmox_endpoint" {
  description = "Proxmox API endpoint URL (must be HTTPS)"
  type        = string
  validation {
    condition     = can(regex("^https://", var.proxmox_endpoint))
    error_message = "Proxmox endpoint must be an HTTPS URL."
  }
}
variable "proxmox_api_token" {
  description = "Proxmox API token in USER@REALM!TOKENID=TOKEN_SECRET format"
  sensitive   = true
  type        = string
  validation {
    condition     = can(regex("^[^@]+@[^!]+!.+=.+$", var.proxmox_api_token))
    error_message = "Proxmox API token must be in USER@REALM!TOKENID=TOKEN_SECRET format."
  }
}
variable "proxmox_node_name" {
  description = "Proxmox node name shown in the UI"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]*$", var.proxmox_node_name))
    error_message = "Node name must start with an alphanumeric character and contain only alphanumeric characters and hyphens."
  }
}
variable "proxmox_insecure_tls" {
  default     = true
  description = "Allow self-signed Proxmox TLS certificates"
  type        = bool
}
