#!/bin/bash
# r2-helpers.sh — Shared helpers for R2 backend setup scripts
#
# Provides: colors, die/info/ok/warn, cf_api, cf_api_verbose,
#           auto-detect account ID, prerequisite checks, R2 config defaults.
#
# This file is meant to be sourced, not executed directly.
# shellcheck disable=SC2034,SC2155

# ──────────────────────────────────────────────
# Colors & helpers
# ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

die()   { echo -e "${RED}ERROR: $*${NC}" >&2; exit 1; }
info()  { echo -e "${CYAN}==>${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }

# ──────────────────────────────────────────────
# Cloudflare API helpers
# ──────────────────────────────────────────────
CF_API_BASE="https://api.cloudflare.com/client/v4"

cf_api() {
  local method="$1"
  local path="$2"
  local data="${3:-}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] curl -X ${method} ${CF_API_BASE}${path} ..."
    return 0
  fi

  local args=(
    -s --fail-with-body
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}"
    -H "Content-Type: application/json"
  )

  if [[ -n "${data}" ]]; then
    args+=(-d "${data}")
  fi

  curl "${args[@]}" -X "${method}" "${CF_API_BASE}${path}" 2>/dev/null || {
    local rc=$?
    die "API request failed (exit ${rc}): ${method} ${path}"
  }
}

cf_api_verbose() {
  # Like cf_api but prints the error body on failure
  local method="$1"
  local path="$2"
  local data="${3:-}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] curl -X ${method} ${CF_API_BASE}${path} ..."
    return 0
  fi

  local args=(
    -s
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}"
    -H "Content-Type: application/json"
  )

  if [[ -n "${data}" ]]; then
    args+=(-d "${data}")
  fi

  local response
  response=$(curl "${args[@]}" -X "${method}" "${CF_API_BASE}${path}" 2>/dev/null) || {
    local rc=$?
    die "API request failed (exit ${rc}): ${method} ${path}"
  }

  local success
  success=$(echo "${response}" | jq -r '.success' 2>/dev/null || echo "false")

  if [[ "${success}" != "true" ]]; then
    local errors
    errors=$(echo "${response}" | jq -c '.errors' 2>/dev/null || echo "unknown error")
    die "API error: ${method} ${path} — ${errors}"
  fi

  echo "${response}"
}

# ──────────────────────────────────────────────
# R2 defaults from generated shell defaults
# ──────────────────────────────────────────────
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R2_DEFAULTS_FILE="${LIB_DIR}/r2-defaults.sh"

if [[ -f "$R2_DEFAULTS_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$R2_DEFAULTS_FILE"
fi

get_default_bucket_name() { echo "${R2_DEFAULT_BUCKET_NAME:-autolab-opentofu-state}"; }
get_default_r2_region() { echo "${R2_DEFAULT_REGION:-auto}"; }
get_default_token_name() { echo "${R2_DEFAULT_TOKEN_NAME:-autolab-opentofu-state}"; }

# ──────────────────────────────────────────────
# Auto-detect account ID from API token
# ──────────────────────────────────────────────
detect_account_id() {
  if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
    info "No account ID provided — auto-detecting from API token..."
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
      info "[dry-run] Would call GET /accounts to discover account ID"
      CLOUDFLARE_ACCOUNT_ID="<auto-detected-in-dry-run>"
    else
      local accounts_response
      accounts_response=$(cf_api GET "/accounts")
      CLOUDFLARE_ACCOUNT_ID=$(echo "${accounts_response}" | jq -r '.result[0].id // empty')
      if [[ -z "${CLOUDFLARE_ACCOUNT_ID}" ]]; then
        die "Could not auto-detect account ID. Ensure the API token has account read permissions, or provide --account-id explicitly."
      fi
      ok "Detected account ID: ${CLOUDFLARE_ACCOUNT_ID}"
    fi
  fi
}

# ──────────────────────────────────────────────
# Prerequisite checks
# ──────────────────────────────────────────────
check_prerequisites() {
  # jq is required
  if ! command -v jq &>/dev/null; then
    die "jq is required. Install it:
  brew install jq          # macOS
  sudo apt install jq      # Debian/Ubuntu
  sudo dnf install jq      # Fedora"
  fi

  # curl is required
  if ! command -v curl &>/dev/null; then
    die "curl is required but not found."
  fi

  # API token
  if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    die "Cloudflare API token is required.
Provide it via the CLOUDFLARE_API_TOKEN env var or the --api-token flag."
  fi
}

# ──────────────────────────────────────────────
# Parse common R2 CLI arguments
# ──────────────────────────────────────────────
# Parses --api-token, --account-id, --bucket-name, --dry-run, -h/--help.
# Sets: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, BUCKET_NAME, DRY_RUN
# Unrecognized arguments are stored in the global array R2_REMAINING_ARGS.
# Each sourcing script must define a usage() function before calling this.
parse_r2_args() {
  R2_REMAINING_ARGS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --api-token)   CLOUDFLARE_API_TOKEN="$2"; shift 2 ;;
      --account-id)  CLOUDFLARE_ACCOUNT_ID="$2"; shift 2 ;;
      --bucket-name) BUCKET_NAME="$2"; shift 2 ;;
      --dry-run)     DRY_RUN=1; shift ;;
      -h|--help)     SHOW_HELP=1; shift ;;
      *)             R2_REMAINING_ARGS+=("$1"); shift ;;
    esac
  done
}

# ──────────────────────────────────────────────
# Shared CLI entry point for R2 scripts.
# ──────────────────────────────────────────────
# Usage:
#   1. Source this file
#   2. Define r2_action() and r2_action_usage() functions
#   3. Optionally set defaults (BUCKET_NAME, TOKEN_NAME, etc.)
#   4. Call r2_main "$@"
#
# r2_action() is called after prerequisites are checked and account is detected.
#   It receives remaining (non-common) positional arguments.
# r2_action_usage() should print action-specific usage text (calls r2_usage for common options).

# Print common R2 CLI options.
r2_usage() {
  cat <<EOF
  --api-token TOKEN    Cloudflare API token (or CLOUDFLARE_API_TOKEN env var)
  --account-id ID      Cloudflare account ID (or CLOUDFLARE_ACCOUNT_ID env var;
                       auto-detected from token if omitted)
  --bucket-name NAME   R2 bucket name (default: generated shell defaults)
  --dry-run            Show what would be done without making API calls
  -h, --help           Show this help message and exit
EOF
}

r2_main() {
  parse_r2_args "$@"
  # Use safe expansion syntax for compatibility with old bash (macOS default 3.2)
  # where ${array[@]} on an empty/unset array triggers "unbound variable" with set -u.
  set -- "${R2_REMAINING_ARGS[@]+"${R2_REMAINING_ARGS[@]}"}"

  # Handle help flag
  if [[ "${SHOW_HELP:-0}" -eq 1 ]]; then
    r2_action_usage
    exit 0
  fi

  check_prerequisites
  detect_account_id

  r2_action "$@"
}
