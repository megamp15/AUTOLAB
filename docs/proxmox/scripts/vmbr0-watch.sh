#!/bin/bash
# Re-attach USB Ethernet to the configured Proxmox bridge when replugged.
# Installed to /usr/local/bin/ by install-vmbr0-watch.sh.
# Reads ETH_USB and VMBR from /etc/default/network-uplink-failover at runtime
# so it stays in sync with the network env file.
set -euo pipefail

[[ -f /etc/default/network-uplink-failover ]] && source /etc/default/network-uplink-failover

ETH_USB="${ETH_USB:-}"
VMBR="${VMBR:-vmbr0}"

while true; do
    if [[ -n "${ETH_USB}" ]] && ip link show "${ETH_USB}" &>/dev/null; then
        if ! bridge link show | grep -q "${ETH_USB}"; then
            echo "$(date): Re-enslaving ${ETH_USB} to ${VMBR}..."
            ip link set "${ETH_USB}" up
            sleep 1
            ip link set "${ETH_USB}" master "${VMBR}"
            ip link set "${VMBR}" up
            echo "$(date): Done."
        fi
    fi
    sleep 3
done
