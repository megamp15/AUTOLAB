zone_name   = "pmahir.space"
tunnel_name = "autolab"

# Public sign-in, shared links and the QR admin page (behind the passkey, for
# people who are not on the tailnet). Operator dashboards use the private
# *.lab names and have no Cloudflare DNS record or tunnel ingress rule.
public_hostnames = {
  auth  = { comment = "Pocket ID, the login page itself" }
  share = { comment = "Immich shared links only, through Immich Public Proxy" }
  qr    = { comment = "QR code admin page, behind the Pocket ID passkey" }
}
