# The Cloudflare stack: the zone's public records and the tunnel that serves
# them. It creates nothing on Proxmox and never joins the tailnet, so it
# imports none of the Proxmox base: its versions.tf is generated here, with
# the same R2 backend the other stacks use.

stack {
  id          = "528174e2-60e0-4387-96da-1f4a1b89a29c"
  name        = "Cloudflare"
  description = "pmahir.space records and the tunnel behind them"
  tags        = ["cloudflare", "ingress"]
}

generate_hcl "versions.tf" {
  content {
    terraform {
      required_version = ">= 1.12.5"

      required_providers {
        cloudflare = {
          source  = "cloudflare/cloudflare"
          version = "~> 5.25"
        }
      }

      # Same state bucket as the Proxmox stacks; the endpoint comes from
      # -backend-config in CI. See docs/gitops/05-r2-state-backend.md.
      backend "s3" {
        bucket = global.r2_bucket
        key    = "${terramate.stack.path.relative}/terraform.tfstate"
        region = global.r2_region

        skip_credentials_validation = true
        skip_requesting_account_id  = true
        skip_metadata_api_check     = true
        skip_region_validation      = true
      }
    }
  }
}
