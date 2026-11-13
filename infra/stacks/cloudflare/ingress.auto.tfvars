zone_name   = "pmahir.space"
tunnel_name = "autolab"

# Public sign-in and shared links only. Operator dashboards use the private
# *.lab names and have no Cloudflare DNS record or tunnel ingress rule.
public_hostnames = {
  auth  = { comment = "Pocket ID, the login page itself" }
  share = { comment = "Immich shared links only, through Immich Public Proxy" }
}
