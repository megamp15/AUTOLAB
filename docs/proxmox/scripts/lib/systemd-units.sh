#!/bin/bash
# Systemd unit rendering and installation helpers (source from other scripts).
#
# Provides: render_failover_unit, render_vmbr0_watch_unit, install_unit

# Render the network-uplink-failover.service unit content to stdout.
render_failover_unit() {
  cat << 'EOF'
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
}

# Render the vmbr0-watch.service unit content to stdout.
render_vmbr0_watch_unit() {
  cat << 'EOF'
[Unit]
Description=Re-attach USB Ethernet to vmbr0 when replugged

[Service]
Type=simple
ExecStart=/usr/local/bin/vmbr0-watch.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

# Install a systemd unit file and enable it.
# Usage: install_unit UNIT_NAME UNIT_CONTENT
#   UNIT_NAME    — e.g. "network-uplink-failover.service"
#   UNIT_CONTENT — the unit file content (piped or from render_*)
install_unit() {
  local unit_name="$1"
  local unit_content
  unit_content="$(cat)"
  local unit_path="/etc/systemd/system/${unit_name}"

  echo "${unit_content}" > "${unit_path}"
  systemctl daemon-reload
  systemctl enable --now "${unit_name}"
  systemctl --no-pager status "${unit_name}"
}
