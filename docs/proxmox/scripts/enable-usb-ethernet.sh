#!/bin/bash
# Plug in USB Ethernet, then run this to set ETH_USB and apply vmbr0 + vmbr0-watch.
# Requires /etc/default/proxmox-network.env from configure-proxmox-network-env.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/detect.sh
source "${SCRIPT_DIR}/lib/detect.sh"
# shellcheck source=lib/env-config.sh
source "${SCRIPT_DIR}/lib/env-config.sh"
CONFIG="${CONFIG:-/etc/default/proxmox-network.env}"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "==> $*"; }

[[ "$(id -u)" -eq 0 ]] || die "Run as root"
[[ -f "${CONFIG}" ]] || die "Missing ${CONFIG}. Run configure-proxmox-network-env.sh first."

ETH_USB="$(detect_iface '^enx')"
[[ -n "${ETH_USB}" ]] || die "No USB Ethernet (enx*) found. Plug the adapter/hub, wait a few seconds, then retry."

log "Detected USB Ethernet: ${ETH_USB}"
env_file_set "${CONFIG}" ETH_USB "${ETH_USB}"

log "Updated ${CONFIG}"
grep '^ETH_USB=' "${CONFIG}"

log "Applying network setup (vmbr0 + vmbr0-watch)..."
bash "${SCRIPT_DIR}/setup-proxmox-network.sh" --apply --skip-apt