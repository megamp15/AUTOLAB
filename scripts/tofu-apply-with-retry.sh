#!/bin/bash
# tofu-apply-with-retry.sh — Run tofu apply with automatic retries
#
# Usage:
#   tofu-apply-with-retry.sh <plan-file> [parallelism] [max-retries] [retry-delay]
#
# Arguments:
#   plan-file     Path to the saved plan file (required)
#   parallelism   OpenTofu parallelism (default: 1)
#   max-retries   Number of retry attempts (default: 3)
#   retry-delay   Seconds to wait between retries (default: 30)
#
# Environment variables:
#   TF_VAR_*      Passed through to tofu apply
#   R2_ENDPOINT    Used for backend config if set
#
# Exit codes:
#   0  Apply succeeded
#   1  Apply failed after all retries
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/retry.sh"

PLAN_FILE="${1:?Usage: tofu-apply-with-retry.sh <plan-file> [parallelism] [max-retries] [retry-delay]}"
PARALLELISM="${2:-1}"
MAX_RETRIES="${3:-3}"
RETRY_DELAY="${4:-30}"

retry_init "$MAX_RETRIES" "$RETRY_DELAY"

if retry_loop tofu apply -input=false -auto-approve -no-color -parallelism="$PARALLELISM" "$PLAN_FILE" | tee apply.txt; then
  echo "✅ Apply succeeded"
else
  echo "❌ Apply failed after $MAX_RETRIES attempts"
  exit 1
fi