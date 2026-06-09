#!/bin/bash
# r2-create-token.sh — Create an R2 API token with Object Read & Write permissions
#
# Standalone script that creates a Cloudflare R2 API token scoped to a bucket.
# Outputs ACCESS_KEY_ID and SECRET_ACCESS_KEY on separate lines for machine parsing.
#
# Usage:
#   bash scripts/r2-create-token.sh --api-token TOKEN [--account-id ID] [--token-name NAME] [--bucket-name NAME] [--dry-run]
#
# Prerequisites:
#   - Cloudflare API token with R2 edit permissions
#   - jq, curl
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/r2-helpers.sh
source "${SCRIPT_DIR}/lib/r2-helpers.sh"

# Keep stdout machine-clean for --format json, including common helper messages
# emitted before r2_action runs (for example account auto-detection).
info()  { echo -e "${CYAN}==>${NC} $*" >&2; }
ok()    { echo -e "${GREEN}✓${NC} $*" >&2; }
warn()  { echo -e "${YELLOW}⚠${NC} $*" >&2; }

# ──────────────────────────────────────────────
# Defaults (overridable via env vars or flags)
# ──────────────────────────────────────────────
BUCKET_NAME="${BUCKET_NAME:-$(get_default_bucket_name)}"
TOKEN_NAME="${TOKEN_NAME:-$(get_default_token_name)}"
CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"
DRY_RUN=0
FORMAT="${FORMAT:-text}"

# ──────────────────────────────────────────────
# Action Usage
# ──────────────────────────────────────────────
r2_action_usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Create an R2 API token with Object Read & Write permissions on a bucket.

Options:
$(r2_usage)
  --token-name NAME    R2 API token name (default: ${TOKEN_NAME})
  --format text|json   Output format (default: ${FORMAT})
EOF
  exit 0
}

# ──────────────────────────────────────────────
# Action: Create R2 API token
# ──────────────────────────────────────────────
r2_action() {
  # Parse script-specific flags
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --token-name)  TOKEN_NAME="$2"; shift 2 ;;
      --format)      FORMAT="$2"; shift 2 ;;
      *) echo "Unknown option: $1"; r2_action_usage ;;
    esac
  done

  # Validate format
  case "${FORMAT}" in
    text|json) ;;
    *) die "Invalid format '${FORMAT}'. Use 'text' or 'json'." ;;
  esac

  # Send progress messages to stderr so stdout stays clean for machine parsing
  info "Creating R2 API token '${TOKEN_NAME}'..." >&2
  ACCESS_KEY_ID=""
  SECRET_ACCESS_KEY=""

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    info "[dry-run] Would create API token '${TOKEN_NAME}' with Object Read & Write on bucket '${BUCKET_NAME}'" >&2
    ACCESS_KEY_ID="<dry-run-access-key-id>"
    SECRET_ACCESS_KEY="<dry-run-secret-access-key>"
  else
    token_response=$(cf_api_verbose POST "/accounts/${CLOUDFLARE_ACCOUNT_ID}/r2/tokens" \
      "$(jq -n \
        --arg name "${TOKEN_NAME}" \
        --arg bucket "${BUCKET_NAME}" \
        '{
          name: $name,
          permissions: {
            objects: {
              read: [{bucket: $bucket, prefix: "*"}],
              write: [{bucket: $bucket, prefix: "*"}]
            }
          }
        }')")

    ACCESS_KEY_ID=$(echo "${token_response}" | jq -r '.result.access_key_id // empty')
    SECRET_ACCESS_KEY=$(echo "${token_response}" | jq -r '.result.secret_access_key // empty')

    if [[ -z "${ACCESS_KEY_ID}" || -z "${SECRET_ACCESS_KEY}" ]]; then
      die "Failed to retrieve access credentials from API response.
Response: $(echo "${token_response}" | jq -c '.')"
    fi

    ok "API token '${TOKEN_NAME}' created." >&2
  fi

  # Emit credentials in the requested format
  if [[ "${FORMAT}" == "json" ]]; then
    jq -n \
      --arg key "${ACCESS_KEY_ID}" \
      --arg secret "${SECRET_ACCESS_KEY}" \
      '{access_key_id: $key, secret_access_key: $secret}'
  else
    echo "ACCESS_KEY_ID=${ACCESS_KEY_ID}"
    echo "SECRET_ACCESS_KEY=${SECRET_ACCESS_KEY}"
  fi
}

r2_main "$@"
