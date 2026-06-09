#!/bin/bash
# Install network-uplink-failover on a Proxmox node (run as root).
# Requires ETH_USB, WIFI, GW, VMBR, VMBR_IP — usually set by setup-proxmox-network.sh via env file.
set -euo pipefail

: "${WIFI:?Set WIFI}"
: "${GW:?Set GW}"
: "${VMBR_IP:?Set VMBR_IP}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/proxmox-env.sh
source "${SCRIPT_DIR}/lib/proxmox-env.sh"
# shellcheck source=lib/systemd-units.sh
source "${SCRIPT_DIR}/lib/systemd-units.sh"

mkdir -p /usr/local/lib/proxmox-network
install -m 644 "${SCRIPT_DIR}/lib/detect.sh" /usr/local/lib/proxmox-network/detect.sh
install -m 644 "${SCRIPT_DIR}/lib/failover-logic.sh" /usr/local/lib/proxmox-network/failover-logic.sh
install -m 755 "${SCRIPT_DIR}/network-uplink-failover.sh" /usr/local/bin/network-uplink-failover.sh

write_failover_env /etc/default/network-uplink-failover

render_failover_unit | install_unit "network-uplink-failover.service"
