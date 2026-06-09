#!/bin/bash
# resolve-packer-template.sh — Resolve a Packer template name to build metadata.
#
# Interface:
#   bash scripts/resolve-packer-template.sh TEMPLATE [--github-env]
#
# The Packer template catalog is intentionally small: callers choose a template
# name, and this module owns the mapping to files and default metadata.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${1:-}"
EMIT_GITHUB_ENV=0

if [[ -z "${TEMPLATE}" || "${TEMPLATE}" == "-h" || "${TEMPLATE}" == "--help" ]]; then
  cat <<'EOF'
Usage: resolve-packer-template.sh TEMPLATE [--github-env]

Known templates:
  debian-12  Debian 12 cloud-init template

Outputs shell key=value lines by default. With --github-env, writes the same
values to GITHUB_ENV using scripts/lib/github-env.sh.
EOF
  exit 0
fi

shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --github-env) EMIT_GITHUB_ENV=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

case "${TEMPLATE}" in
  debian-12)
    AUTOLAB_PACKER_TEMPLATE="debian-12"
    AUTOLAB_PACKER_TEMPLATE_FILE="infra/packer/debian-12.pkr.hcl"
    AUTOLAB_PACKER_TEMPLATE_DIR="infra/packer"
    AUTOLAB_PACKER_TEMPLATE_DESCRIPTION="Debian 12 cloud-init template"
    ;;
  *)
    echo "ERROR: Unknown Packer template '${TEMPLATE}'. Known templates: debian-12" >&2
    exit 1
    ;;
esac

if [[ "${EMIT_GITHUB_ENV}" -eq 1 ]]; then
  # shellcheck source=lib/github-env.sh
  source "${REPO_ROOT}/scripts/lib/github-env.sh"
  append_github_env "AUTOLAB_PACKER_TEMPLATE" "${AUTOLAB_PACKER_TEMPLATE}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_FILE" "${AUTOLAB_PACKER_TEMPLATE_FILE}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_DIR" "${AUTOLAB_PACKER_TEMPLATE_DIR}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_DESCRIPTION" "${AUTOLAB_PACKER_TEMPLATE_DESCRIPTION}"
else
  printf 'AUTOLAB_PACKER_TEMPLATE=%s\n' "${AUTOLAB_PACKER_TEMPLATE}"
  printf 'AUTOLAB_PACKER_TEMPLATE_FILE=%s\n' "${AUTOLAB_PACKER_TEMPLATE_FILE}"
  printf 'AUTOLAB_PACKER_TEMPLATE_DIR=%s\n' "${AUTOLAB_PACKER_TEMPLATE_DIR}"
  printf 'AUTOLAB_PACKER_TEMPLATE_DESCRIPTION=%s\n' "${AUTOLAB_PACKER_TEMPLATE_DESCRIPTION}"
fi
