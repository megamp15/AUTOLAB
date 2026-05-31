#!/bin/bash
# Install network-uplink-failover on a Proxmox node (run as root).
# Requires ETH_USB, WIFI, GW, VMBR_IP — usually set by setup-proxmox-network.sh via env file.
set -euo pipefail

: "${WIFI:?Set WIFI}"
: "${GW:?Set GW}"
: "${VMBR_IP:?Set VMBR_IP}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/proxmox-env.sh
source "${SCRIPT_DIR}/lib/proxmox-env.sh"

install -m 755 "${SCRIPT_DIR}/network-uplink-failover.sh" /usr/local/bin/network-uplink-failover.sh

write_failover_env /etc/default/network-uplink-failover

cat > /etc/systemd/system/network-uplink-failover.service << 'EOF'
[Unit]
Description=Ethernet/Wi-Fi default route failover
After=networking.service
Wants=networking.service

[Service]
Type=simple
EnvironmentFile=-/etc/default/network-uplink-failover
ExecStartPre=/usr/local/bin/network-uplink-failover.sh --once
ExecStart=/usr/local/bin/network-uplink-failover.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now network-uplink-failover
echo "Installed network-uplink-failover. Status:"
systemctl --no-pager status network-uplink-failover
