#!/bin/bash
# validate-connection-schema.sh — Check that OpenTofu, Packer, and CI adapters
# stay in sync with the connection schema in infra/connection-schema.yaml.
#
# Now delegates to generate-connection-adapters.sh --check.
#
# Run from the repo root:
#   bash scripts/validate-connection-schema.sh
#
# Exit 0 if all adapters match the schema, exit 1 on drift.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${SCRIPT_DIR}/generate-connection-adapters.sh" --check
