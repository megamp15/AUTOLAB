#!/bin/bash
# Install vmbr0-watch on a Proxmox node (run as root).
set -euo pipefail

: "${ETH_USB:?Set ETH_USB (or leave empty in env if no USB NIC yet)}"

cat > /usr/local/bin/vmbr0-watch.sh << EOF
#!/bin/bash
ETH_USB="${ETH_USB}"
while true; do
    if [[ -n "\$ETH_USB" ]] && ip link show "\$ETH_USB" &>/dev/null; then
        if ! bridge link show | grep -q "\$ETH_USB"; then
            echo "\$(date): Re-enslaving \${ETH_USB} to vmbr0..."
            ip link set "\$ETH_USB" up
            sleep 1
            ip link set "\$ETH_USB" master vmbr0
            ip link set vmbr0 up
            echo "\$(date): Done."
        fi
    fi
    sleep 3
done
EOF
chmod +x /usr/local/bin/vmbr0-watch.sh

cat > /etc/systemd/system/vmbr0-watch.service << 'EOF'
[Unit]
Description=Re-attach USB Ethernet to vmbr0 when replugged

[Service]
Type=simple
ExecStart=/usr/local/bin/vmbr0-watch.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now vmbr0-watch
systemctl --no-pager status vmbr0-watch
