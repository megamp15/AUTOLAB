#!/bin/bash
# setup-r2-backend.sh — Create Cloudflare R2 bucket + API token for OpenTofu state
#
# Thin orchestrator that calls r2-create-bucket.sh then r2-create-token.sh
# and prints a summary with next steps.
#
# Prerequisites:
#   - Cloudflare account with R2 enabled
#   - Cloudflare API token with R2 edit permissions
#   - jq (install: brew install jq / apt install jq)
#   - curl (usually pre-installed)
#
# Usage:
#   export CLOUDFLARE_API_TOKEN="…"
#   export CLOUDFLARE_ACCOUNT_ID="…"          # optional — auto-detected if omitted
#   bash scripts/setup-r2-backend.sh
#
#   # Or pass flags:
#   bash scripts/setup-r2-backend.sh \
#     --api-token "$CF_TOKEN" \
#     --account-id "$CF_ACCOUNT_ID" \
#     --bucket-name "autolab-opentofu-state" \
#     --token-name "autolab-opentofu-state" \
#     --dry-run \
#     --format json
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/r2-helpers.sh
source "${SCRIPT_DIR}/lib/r2-helpers.sh"

# ──────────────────────────────────────────────
# Defaults (overridable via env vars or flags)
# ──────────────────────────────────────────────
BUCKET_NAME="${BUCKET_NAME:-$(get_default_bucket_name)}"
TOKEN_NAME="$(get_default_token_name)"
CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"
DRY_RUN=0
FORMAT="${FORMAT:-text}"

# Keep stdout machine-clean when callers ask for JSON. This pre-scan must happen
# before r2_main because common helpers can log before r2_action parses flags.
for arg in "$@"; do
  if [[ "${arg}" == "json" ]]; then
    info()  { echo -e "${CYAN}==>${NC} $*" >&2; }
    ok()    { echo -e "${GREEN}✓${NC} $*" >&2; }
    warn()  { echo -e "${YELLOW}⚠${NC} $*" >&2; }
    break
  fi
done

# ──────────────────────────────────────────────
# Action Usage
# ──────────────────────────────────────────────
r2_action_usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Create Cloudflare R2 bucket + API token for OpenTofu state.

Options:
$(r2_usage)
  --token-name NAME    R2 API token name (default: ${TOKEN_NAME})
  --format text|json   Output format for the setup result (default: ${FORMAT})
EOF
  exit 0
}

# ──────────────────────────────────────────────
# Action: orchestrate bucket + token creation
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

  case "${FORMAT}" in
    text|json) ;;
    *) die "Invalid format '${FORMAT}'. Use 'text' or 'json'." ;;
  esac

  # Step 1: Create bucket
  info "Step 1: Ensuring R2 bucket '${BUCKET_NAME}' exists..."
  BUCKET_OUTPUT=$(bash "${SCRIPT_DIR}/r2-create-bucket.sh" \
    --api-token "$CLOUDFLARE_API_TOKEN" \
    --account-id "$CLOUDFLARE_ACCOUNT_ID" \
    --bucket-name "$BUCKET_NAME" \
    ${DRY_RUN:+--dry-run})
  if [[ -n "${BUCKET_OUTPUT}" ]]; then
    if [[ "${FORMAT}" == "json" ]]; then
      printf '%s\n' "${BUCKET_OUTPUT}" >&2
    else
      printf '%s\n' "${BUCKET_OUTPUT}"
    fi
  fi

  # Step 2: Create token
  info "Step 2: Creating R2 API token '${TOKEN_NAME}'..."
  TOKEN_JSON=$(bash "${SCRIPT_DIR}/r2-create-token.sh" \
    --api-token "$CLOUDFLARE_API_TOKEN" \
    --account-id "$CLOUDFLARE_ACCOUNT_ID" \
    --bucket-name "$BUCKET_NAME" \
    --token-name "$TOKEN_NAME" \
    --format json \
    ${DRY_RUN:+--dry-run})

  # Capture credentials from token JSON output
  ACCESS_KEY_ID=$(echo "${TOKEN_JSON}" | jq -r '.access_key_id')
  SECRET_ACCESS_KEY=$(echo "${TOKEN_JSON}" | jq -r '.secret_access_key')

  if [[ -z "${ACCESS_KEY_ID}" || "${ACCESS_KEY_ID}" == "null" || -z "${SECRET_ACCESS_KEY}" || "${SECRET_ACCESS_KEY}" == "null" ]]; then
    die "Failed to parse R2 token credentials from JSON output."
  fi

  R2_ENDPOINT="https://${CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

  if [[ "${FORMAT}" == "json" ]]; then
    jq -n \
      --arg bucket_name "${BUCKET_NAME}" \
      --arg token_name "${TOKEN_NAME}" \
      --arg account_id "${CLOUDFLARE_ACCOUNT_ID}" \
      --arg endpoint "${R2_ENDPOINT}" \
      --arg access_key_id "${ACCESS_KEY_ID}" \
      --arg secret_access_key "${SECRET_ACCESS_KEY}" \
      '{bucket_name: $bucket_name, token_name: $token_name, account_id: $account_id, endpoint: $endpoint, github_environment: {secrets: {R2_ACCESS_KEY_ID: $access_key_id, R2_SECRET_ACCESS_KEY: $secret_access_key}, variables: {R2_ACCOUNT_ID: $account_id}}, local_environment: {AWS_ACCESS_KEY_ID: $access_key_id, AWS_SECRET_ACCESS_KEY: $secret_access_key, R2_ENDPOINT: $endpoint}}'
    return 0
  fi

  # ──────────────────────────────────────────────
  # Step 3: Print summary
  # ──────────────────────────────────────────────
  echo ""
  echo "══════════════════════════════════════════════════════════════"
  echo "                   SETUP COMPLETE"
  echo "══════════════════════════════════════════════════════════════"
  echo ""

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo -e "${YELLOW}⚠ Dry-run mode — no changes were made.${NC}"
    echo "Re-run without --dry-run to apply."
    echo ""
  fi

  echo -e "${GREEN}R2 Bucket:${NC}        ${BUCKET_NAME} (from infra/r2-config.yaml)"
  echo -e "${GREEN}R2 Token:${NC}         ${TOKEN_NAME}"
  echo -e "${GREEN}Account ID:${NC}       ${CLOUDFLARE_ACCOUNT_ID}"
  echo -e "${GREEN}R2 Endpoint:${NC}      ${R2_ENDPOINT}"
  echo ""

  echo -e "${CYAN}── GitHub Environment Secrets ──${NC}"
  echo "Add these to your GitHub repository secrets:"
  echo ""
  echo "  R2_ACCESS_KEY_ID=${ACCESS_KEY_ID}"
  echo "  R2_SECRET_ACCESS_KEY=${SECRET_ACCESS_KEY}"
  echo ""

  echo -e "${CYAN}── Local Environment Variables ──${NC}"
  echo "Set these before running 'tofu init':"
  echo ""
  echo "  export AWS_ACCESS_KEY_ID=${ACCESS_KEY_ID}"
  echo "  export AWS_SECRET_ACCESS_KEY=${SECRET_ACCESS_KEY}"
  echo ""

  echo -e "${CYAN}── Next Step ──${NC}"
  echo "Generate Terramate configs and initialize the state backend:"
  echo ""
  echo "  cd infra"
  echo "  terramate generate"
  echo "  cd stacks/lab"
  echo "  tofu init -backend-config=\"endpoint=${R2_ENDPOINT}\""
  echo ""
  echo "══════════════════════════════════════════════════════════════"
}

r2_main "$@"
