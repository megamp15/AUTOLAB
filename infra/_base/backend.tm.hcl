generate_hcl "versions.tf" {
  content {
    terraform {
      required_version = ">= 1.9.0"

      required_providers {
        proxmox = {
          source  = "bpg/proxmox"
          version = "~> 0.107"
        }
      }

      # State is stored in Cloudflare R2 (S3-compatible).
      # Sensitive credentials are passed via CLI flags in GitHub Actions.
      # For local use, set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars.
      # The R2 endpoint is passed via -backend-config in CI (not stored here).
      # See docs/gitops/05-r2-state-backend.md for setup instructions.
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