#!/bin/bash
# Re-install /usr/local/bin network scripts from the repo copy on this host.
# Run ON the Proxmox host as root (not from your laptop).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-/etc/default/proxmox-network.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Create from config/network.env.example first." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "${ENV_FILE}"
VMBR="${VMBR:-vmbr0}"

: "${WIFI:?WIFI not set in ${ENV_FILE}}"
: "${GW:?GW not set in ${ENV_FILE}}"
: "${VMBR_IP:?VMBR_IP not set in ${ENV_FILE}}"

echo "==> Installing network-uplink-failover from ${SCRIPT_DIR}"
ETH_USB="${ETH_USB:-}" WIFI="${WIFI}" GW="${GW}" VMBR="${VMBR}" VMBR_IP="${VMBR_IP}" \
  bash "${SCRIPT_DIR}/install-network-uplink-failover.sh"

if [[ -n "${ETH_USB:-}" ]]; then
  echo "==> Installing vmbr0-watch from ${SCRIPT_DIR}"
  bash "${SCRIPT_DIR}/install-vmbr0-watch.sh"
else
  echo "==> Skipping vmbr0-watch (ETH_USB empty in ${ENV_FILE})"
fi

systemctl restart network-uplink-failover
/usr/local/bin/network-uplink-failover.sh --once

if [[ -f /usr/local/lib/proxmox-network/failover-logic.sh ]] \
   && grep -q 'apply_state' /usr/local/lib/proxmox-network/failover-logic.sh; then
  echo "OK: failover logic installed"
else
  echo "MISMATCH: failover logic not found, re-copy repo and run again" >&2
  exit 1
fi

if cmp -s "${SCRIPT_DIR}/network-uplink-failover.sh" /usr/local/bin/network-uplink-failover.sh; then
  echo "OK: /usr/local/bin/network-uplink-failover.sh matches repo"
fi

echo ""
ip -br addr show dev "${VMBR}" 2>/dev/null || true
ip -br addr show dev "${WIFI}" 2>/dev/null || true
ip route get 8.8.8.8 2>/dev/null || true
