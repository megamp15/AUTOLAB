#!/bin/bash
# r2-create-bucket.sh — Create an R2 bucket (idempotent)
#
# Standalone script that creates a Cloudflare R2 bucket if it does not exist.
# Skips successfully if the bucket already exists.
#
# Usage:
#   bash scripts/r2-create-bucket.sh --api-token TOKEN [--account-id ID] [--bucket-name NAME] [--dry-run]
#
# Prerequisites:
#   - Cloudflare API token with R2 edit permissions
#   - jq, curl
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/r2-helpers.sh
source "${SCRIPT_DIR}/lib/r2-helpers.sh"

# ──────────────────────────────────────────────
# Defaults (overridable via env vars or flags)
# ──────────────────────────────────────────────
BUCKET_NAME="${BUCKET_NAME:-$(get_default_bucket_name)}"
CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"
DRY_RUN=0

# ──────────────────────────────────────────────
# Action Usage
# ──────────────────────────────────────────────
r2_action_usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Create an R2 bucket (idempotent — skips if exists).

Options:
$(r2_usage)
EOF
  exit 0
}

# ──────────────────────────────────────────────
# Action: Create R2 bucket (idempotent)
# ──────────────────────────────────────────────
r2_action() {
  # No script-specific flags expected
  if [[ $# -gt 0 ]]; then
    echo "Unknown option: $1"
    r2_action_usage
  fi

  info "Ensuring R2 bucket '${BUCKET_NAME}' exists..."

  if [[ "${DRY_RUN}" -eq 0 ]]; then
    # Check if bucket already exists
    buckets_json=$(cf_api GET "/accounts/${CLOUDFLARE_ACCOUNT_ID}/r2/buckets")
    bucket_exists=$(echo "${buckets_json}" | jq -r --arg name "${BUCKET_NAME}" '
      .result[] | select(.name == $name) | .name
    ')

    if [[ -n "${bucket_exists}" ]]; then
      ok "Bucket '${BUCKET_NAME}' already exists — skipping creation."
    else
      info "Creating bucket '${BUCKET_NAME}'..."
      cf_api_verbose POST "/accounts/${CLOUDFLARE_ACCOUNT_ID}/r2/buckets" \
        "$(jq -n --arg name "${BUCKET_NAME}" '{name: $name}')" >/dev/null
      ok "Bucket '${BUCKET_NAME}' created."
    fi
  else
    info "[dry-run] Would check if bucket '${BUCKET_NAME}' exists"
    info "[dry-run] Would create bucket '${BUCKET_NAME}' if it does not exist"
  fi
}

r2_main "$@"
