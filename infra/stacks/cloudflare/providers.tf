provider "cloudflare" {
  # A token scoped to this zone (DNS: Edit) and this account (Cloudflare
  # Tunnel: Edit), nothing else. The thing that writes DNS has no business
  # doing anything else — the same discipline as the read-only Proxmox token.
  api_token = var.cloudflare_api_token
}
