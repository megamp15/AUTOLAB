output "tunnel_id" {
  description = "UUID of the tunnel; its CNAME target is <id>.cfargotunnel.com."
  value       = cloudflare_zero_trust_tunnel_cloudflared.autolab.id
}

output "zone_name" {
  description = "The domain the hostnames live under."
  value       = var.zone_name
}

output "hostname_labels" {
  description = "Service labels used by ingress and internal URLs; a label does not grant public exposure."
  value       = merge({ home = "home", grafana = "grafana" }, { for label, _ in var.public_hostnames : label => label })
}

output "public_hostnames" {
  description = "The hostnames the tunnel answers for, as created."
  value       = [for r in cloudflare_dns_record.public : r.name]
}

output "tunnel_token" {
  description = "Connector token for cloudflared on horizon. Read by the ingress playbook from state; never printed."
  value       = data.cloudflare_zero_trust_tunnel_cloudflared_token.autolab.token
  sensitive   = true
}

output "internal_label" {
  description = "Sub-label for tailnet-only names (split DNS inside the tailnet, never a public record); empty when none."
  value       = var.internal_label
}
