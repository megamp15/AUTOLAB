# ---------------------------------------------------------------------------
# Packer connection variables — AUTO-GENERATED from infra/connection-schema.yaml
# by scripts/generate-connection-adapters.sh. Do not edit manually.
#
# Template-specific variables are in template-vars.pkr.hcl (hand-maintained).
# ---------------------------------------------------------------------------


variable "proxmox_endpoint" {
  type        = string
  description = "Proxmox API endpoint URL (must be HTTPS)"
}

variable "proxmox_api_token" {
  type        = string
  description = "Proxmox API token in USER@REALM!TOKENID=TOKEN_SECRET format"
  sensitive   = true
}

variable "proxmox_node_name" {
  type        = string
  description = "Proxmox node name shown in the UI"
}

variable "proxmox_insecure_tls" {
  type        = bool
  description = "Allow self-signed Proxmox TLS certificates"
  default     = true
}
