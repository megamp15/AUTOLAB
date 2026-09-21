variable "cloudflare_api_token" {
  description = "API token scoped to the zone (DNS: Edit) and the account (Cloudflare Tunnel: Edit)."
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID. Not a secret; it is in every dashboard URL."
  type        = string
}

variable "cloudflare_zone_id" {
  description = "Zone ID of the domain the public hostnames live under."
  type        = string
}

variable "zone_name" {
  description = "The domain itself, e.g. pmahir.space. Hostnames are labels under it."
  type        = string
}

variable "tunnel_name" {
  description = "Name of the tunnel as the Zero Trust dashboard shows it."
  type        = string
  default     = "autolab"
}

# Every public hostname routes to the same origin: Traefik, inside horizon's
# compose network, which then routes by Host header. Cloudflare only needs to
# know the hostnames exist; who may reach what is decided on horizon.
variable "public_hostnames" {
  description = "Labels under the zone that the tunnel answers for, with the origin cloudflared hands each one to."
  type = map(object({
    service = optional(string, "http://traefik:80")
    comment = optional(string, "")
  }))
  validation {
    condition     = length(var.public_hostnames) > 0
    error_message = "At least one public hostname is required; a tunnel with no ingress rule is refused by Cloudflare."
  }
}
