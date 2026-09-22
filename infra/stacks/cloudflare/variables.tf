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

# The tailnet side is not in public DNS at all. *.<label>.<zone> resolves
# only inside the tailnet (split DNS → a responder on horizon), and the
# certificate's DNS challenge needs no record here beyond the TXT it writes
# itself. The label is declared in this stack so the ingress role and the
# homepage read one source; empty turns the tailnet side off.
variable "internal_label" {
  description = "Sub-label under the zone for tailnet-only names, e.g. lab → *.lab.<zone>. Empty = none."
  type        = string
  default     = "lab"
}
