#!/bin/bash
# resolve-packer-template.sh — Resolve a Packer template name to build metadata.
#
# Interface:
#   bash scripts/resolve-packer-template.sh TEMPLATE [--github-env]
#
# Implemented templates come from infra/packer/template-catalog.yaml.
# Disposable experiment ideas live in the same catalog under experiments and
# in docs/gitops/template-lab-matrix.md until they are promoted.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALOG="${REPO_ROOT}/infra/packer/template-catalog.yaml"
TEMPLATE="${1:-}"
EMIT_GITHUB_ENV=0

if [[ -z "${TEMPLATE}" || "${TEMPLATE}" == "-h" || "${TEMPLATE}" == "--help" ]]; then
  cat <<'EOF'
Usage: resolve-packer-template.sh TEMPLATE [--github-env]

Known implemented templates:
  debian-13  Debian 13 cloud-init template

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

if ! command -v yq &>/dev/null; then
  echo "ERROR: yq is required. Install it: https://github.com/mikefarah/yq" >&2
  exit 1
fi

template_index="$(yq ".templates | to_entries | .[] | select(.value.name == \"${TEMPLATE}\") | .key" "$CATALOG")"
if [[ -z "${template_index}" ]]; then
  experiment_name="$(yq ".experiments[] | select(.name == \"${TEMPLATE}\") | .name" "$CATALOG" 2>/dev/null || true)"
  if [[ -n "${experiment_name}" ]]; then
    echo "ERROR: '${TEMPLATE}' is a disposable experiment target, not an implemented Packer template." >&2
    echo "See docs/gitops/template-lab-matrix.md for the learning menu." >&2
    exit 1
  fi

  known_templates="$(yq -r '.templates[].name' "$CATALOG" | paste -sd ', ' -)"
  echo "ERROR: Unknown Packer template '${TEMPLATE}'. Known implemented templates: ${known_templates}" >&2
  exit 1
fi

status="$(yq -r ".templates[${template_index}].status" "$CATALOG")"
if [[ "${status}" != "implemented" ]]; then
  echo "ERROR: Packer template '${TEMPLATE}' is not implemented (status=${status})." >&2
  exit 1
fi

while IFS= read -r implemented_index; do
  implemented_name="$(yq -r ".templates[${implemented_index}].name" "$CATALOG")"
  implemented_release="$(yq -r ".templates[${implemented_index}].release" "$CATALOG")"
  implemented_iso_url="$(yq -r ".templates[${implemented_index}].iso_url" "$CATALOG")"
  implemented_iso_checksum="$(yq -r ".templates[${implemented_index}].iso_checksum" "$CATALOG")"

  if [[ -z "${implemented_release}" || "${implemented_release}" == "null" ]]; then
    echo "ERROR: Implemented Packer template '${implemented_name}' is missing catalog release metadata." >&2
    exit 1
  fi
  if [[ ! "${implemented_iso_url}" =~ ^https://[^[:space:]]+$ ]]; then
    echo "ERROR: Implemented Packer template '${implemented_name}' has a missing or invalid iso_url." >&2
    exit 1
  fi
  if [[ ! "${implemented_iso_checksum}" =~ ^sha256:[0-9a-fA-F]{64}$ ]]; then
    echo "ERROR: Implemented Packer template '${implemented_name}' has an invalid iso_checksum; expected sha256: plus 64 hex characters." >&2
    exit 1
  fi
done < <(yq -r '.templates | to_entries[] | select(.value.status == "implemented") | .key' "$CATALOG")

AUTOLAB_PACKER_TEMPLATE="$(yq -r ".templates[${template_index}].name" "$CATALOG")"
AUTOLAB_PACKER_TEMPLATE_DIR="$(yq -r ".templates[${template_index}].directory" "$CATALOG")"
packer_file="$(yq -r ".templates[${template_index}].packer_file" "$CATALOG")"
AUTOLAB_PACKER_TEMPLATE_FILE="${AUTOLAB_PACKER_TEMPLATE_DIR}/${packer_file}"
AUTOLAB_PACKER_TEMPLATE_DESCRIPTION="$(yq -r ".templates[${template_index}].description" "$CATALOG")"
AUTOLAB_PACKER_TEMPLATE_STATUS="${status}"
AUTOLAB_PACKER_TEMPLATE_RELEASE="$(yq -r ".templates[${template_index}].release" "$CATALOG")"
AUTOLAB_PACKER_TEMPLATE_VM_ID="$(yq -r ".templates[${template_index}].proxmox_template_vm_id" "$CATALOG")"
AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME="$(yq -r ".templates[${template_index}].proxmox_template_name" "$CATALOG")"
AUTOLAB_PACKER_TEMPLATE_ISO_URL="$(yq -r ".templates[${template_index}].iso_url" "$CATALOG")"
AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM="$(yq -r ".templates[${template_index}].iso_checksum" "$CATALOG")"

if [[ "${EMIT_GITHUB_ENV}" -eq 1 ]]; then
  # shellcheck source=lib/github-env.sh
  source "${REPO_ROOT}/scripts/lib/github-env.sh"
  append_github_env "AUTOLAB_PACKER_TEMPLATE" "${AUTOLAB_PACKER_TEMPLATE}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_FILE" "${AUTOLAB_PACKER_TEMPLATE_FILE}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_DIR" "${AUTOLAB_PACKER_TEMPLATE_DIR}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_DESCRIPTION" "${AUTOLAB_PACKER_TEMPLATE_DESCRIPTION}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_STATUS" "${AUTOLAB_PACKER_TEMPLATE_STATUS}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_RELEASE" "${AUTOLAB_PACKER_TEMPLATE_RELEASE}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_VM_ID" "${AUTOLAB_PACKER_TEMPLATE_VM_ID}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME" "${AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_ISO_URL" "${AUTOLAB_PACKER_TEMPLATE_ISO_URL}"
  append_github_env "AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM" "${AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM}"
  append_github_env "PKR_VAR_vm_id" "${AUTOLAB_PACKER_TEMPLATE_VM_ID}"
  append_github_env "PKR_VAR_vm_template_name" "${AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME}"
  append_github_env "PKR_VAR_iso_url" "${AUTOLAB_PACKER_TEMPLATE_ISO_URL}"
  append_github_env "PKR_VAR_iso_checksum" "${AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM}"
else
  printf 'AUTOLAB_PACKER_TEMPLATE=%q\n' "${AUTOLAB_PACKER_TEMPLATE}"
  printf 'AUTOLAB_PACKER_TEMPLATE_FILE=%q\n' "${AUTOLAB_PACKER_TEMPLATE_FILE}"
  printf 'AUTOLAB_PACKER_TEMPLATE_DIR=%q\n' "${AUTOLAB_PACKER_TEMPLATE_DIR}"
  printf 'AUTOLAB_PACKER_TEMPLATE_DESCRIPTION=%q\n' "${AUTOLAB_PACKER_TEMPLATE_DESCRIPTION}"
  printf 'AUTOLAB_PACKER_TEMPLATE_STATUS=%q\n' "${AUTOLAB_PACKER_TEMPLATE_STATUS}"
  printf 'AUTOLAB_PACKER_TEMPLATE_RELEASE=%q\n' "${AUTOLAB_PACKER_TEMPLATE_RELEASE}"
  printf 'AUTOLAB_PACKER_TEMPLATE_VM_ID=%q\n' "${AUTOLAB_PACKER_TEMPLATE_VM_ID}"
  printf 'AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME=%q\n' "${AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME}"
  printf 'AUTOLAB_PACKER_TEMPLATE_ISO_URL=%q\n' "${AUTOLAB_PACKER_TEMPLATE_ISO_URL}"
  printf 'AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM=%q\n' "${AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM}"
  printf 'PKR_VAR_vm_id=%q\n' "${AUTOLAB_PACKER_TEMPLATE_VM_ID}"
  printf 'PKR_VAR_vm_template_name=%q\n' "${AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME}"
  printf 'PKR_VAR_iso_url=%q\n' "${AUTOLAB_PACKER_TEMPLATE_ISO_URL}"
  printf 'PKR_VAR_iso_checksum=%q\n' "${AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM}"
fi
