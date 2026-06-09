// ---------------------------------------------------------------------------
// Stack connection variables — AUTO-GENERATED from infra/connection-schema.yaml
// by scripts/generate-connection-adapters.sh. Do not edit manually.
//
// This Terramate code-gen block produces a _connection-variables.tf file in
// every stack, declaring the Proxmox connection variables that the provider
// block and the proxmox-connection module both need.
//
// The provider block cannot reference module outputs (a Terraform/OpenTofu
// limitation), so connection variables must be declared at the stack level.
// This generated file ensures they stay in sync with the connection schema.
// ---------------------------------------------------------------------------

generate_hcl "_connection-variables.tf" {
  content {

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
      type        = string
      sensitive   = true
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
      description = "Allow self-signed Proxmox TLS certificates"
      type        = bool
      default     = true
    }
  }
}
