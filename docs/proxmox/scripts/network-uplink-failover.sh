#!/bin/bash
# Ethernet (vmbr0 / USB) vs Wi-Fi failover: default route + single management IP.
# Installed to /usr/local/bin/ by setup-proxmox-network.sh or install-network-uplink-failover.sh
set -euo pipefail

# Source failover logic from installed location (or repo for development)
if [[ -f /usr/local/lib/proxmox-network/failover-logic.sh ]]; then
  # shellcheck source=/dev/null
  source /usr/local/lib/proxmox-network/failover-logic.sh
elif [[ -f "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/failover-logic.sh" ]]; then
  # shellcheck source=lib/failover-logic.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/failover-logic.sh"
fi

[[ -f /etc/default/network-uplink-failover ]] && source /etc/default/network-uplink-failover

ETH_USB="${ETH_USB:-}"
WIFI="${WIFI:-}"
GW="${GW:-}"
VMBR="${VMBR:-vmbr0}"
VMBR_IP="${VMBR_IP:-}"
MGMT_IP="${VMBR_IP%/*}"

[[ -n "${GW}" && -n "${VMBR_IP}" && -n "${WIFI}" ]] \
  || { echo "Missing GW, VMBR_IP, or WIFI in /etc/default/network-uplink-failover" >&2; exit 1; }

case "${1:-}" in
  --once)
    apply_state
    ;;
  *)
    apply_state
    while true; do
      sleep 2
      apply_state
    done
    ;;
esac