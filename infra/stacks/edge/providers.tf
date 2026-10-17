// TERRAMATE: GENERATED AUTOMATICALLY DO NOT EDIT

provider "proxmox" {
  api_token = var.proxmox_api_token
  endpoint  = local.proxmox_endpoint
  insecure  = var.proxmox_insecure_tls
  ssh {
    node {
      address = var.proxmox_host
      name    = var.proxmox_node_name
    }
  }
}
provider "tailscale" {
  scopes = [
    "auth_keys",
  ]
  tailnet = "-"
}
