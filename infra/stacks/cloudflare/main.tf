# One tunnel, remotely managed: its ingress rules live here, not in a YAML
# file on horizon, so a route is a reviewable diff. horizon runs cloudflared
# with the token below and nothing else about the tunnel.
resource "cloudflare_zero_trust_tunnel_cloudflared" "autolab" {
  account_id = var.cloudflare_account_id
  name       = var.tunnel_name
  config_src = "cloudflare"
}

# Hostname → origin. The catch-all is what an unknown hostname gets: a 404
# from cloudflared, never a request to the lab.
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "autolab" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.autolab.id
  config = {
    ingress = concat(
      [
        for label, host in var.public_hostnames : {
          hostname = "${label}.${var.zone_name}"
          service  = host.service
        }
      ],
      [{ service = "http_status:404" }],
    )
  }
}

# Proxied CNAMEs to the tunnel. Proxied is the point: the record resolves to
# Cloudflare, and horizon's address appears nowhere.
resource "cloudflare_dns_record" "public" {
  for_each = var.public_hostnames

  zone_id = var.cloudflare_zone_id
  name    = "${each.key}.${var.zone_name}"
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.autolab.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1 # automatic; required to be 1 for proxied records
  comment = each.value.comment != "" ? each.value.comment : "autolab tunnel, managed by OpenTofu"
}

# The connector's credential. The Builder reads it from this stack's state in
# R2, the way it reads inventories, so it is never pasted anywhere.
data "cloudflare_zero_trust_tunnel_cloudflared_token" "autolab" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.autolab.id
}
