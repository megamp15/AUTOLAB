// TERRAMATE: GENERATED AUTOMATICALLY DO NOT EDIT

variable "proxmox_host" {
  description = "Proxmox host name or IP address (IPv6 literals may be bracketed)"
  type        = string
  validation {
    condition     = can(regex("^[^[:space:]]+$", var.proxmox_host))
    error_message = "Proxmox host must not contain whitespace."
  }
}
variable "proxmox_port" {
  default     = 8006
  description = "Proxmox API HTTPS port"
  type        = number
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
locals {
  proxmox_endpoint     = "https://${local.proxmox_host_for_url}:${var.proxmox_port}"
  proxmox_host_for_url = strcontains(var.proxmox_host, ":") && !startswith(var.proxmox_host, "[") ? "[${var.proxmox_host}]" : var.proxmox_host
}
