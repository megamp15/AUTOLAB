#!/bin/bash
# check-schema-drift.sh — Run all schema/config drift checks.
#
# Interface:
#   bash scripts/check-schema-drift.sh
#
# This is the production-readiness gate for generated adapters. It keeps CI and
# docs from knowing the ordered list of generator modules.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_check() {
  local label="$1"
  shift
  echo "==> ${label}"
  "$@"
}

run_check "Connection adapter drift" \
  bash "${REPO_ROOT}/scripts/generate-connection-adapters.sh" --check

run_check "Packer template adapter drift" \
  bash "${REPO_ROOT}/scripts/generate-packer-template-adapters.sh" --check

run_check "Network env adapter drift" \
  bash "${REPO_ROOT}/scripts/generate-network-env-adapters.sh" --check

run_check "R2 config drift" \
  bash "${REPO_ROOT}/scripts/generate-r2-config.sh" --check

echo ""
echo "Schema drift checks passed."
