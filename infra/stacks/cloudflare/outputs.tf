output "tunnel_id" {
  description = "UUID of the tunnel; its CNAME target is <id>.cfargotunnel.com."
  value       = cloudflare_zero_trust_tunnel_cloudflared.autolab.id
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
