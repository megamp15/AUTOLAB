#!/bin/bash
# Creates an isolated DHCP/NAT network for VMs on Wi-Fi-only Proxmox hosts.
# It does not change the management interface or existing bridges.
set -euo pipefail

BRIDGE="vmbr1"
ADDRESS="10.42.0.1/24"
SUBNET="10.42.0.0/24"
DHCP_START="10.42.0.100"
DHCP_END="10.42.0.200"
DNS_SERVERS="1.1.1.1,1.0.0.1"
APPLY=0

usage() {
  cat <<'EOF'
Usage: setup-private-vm-network.sh [--apply]

Creates vmbr1 with DHCP and NAT through the current default-route interface.
Use --apply to bring the bridge up and start services immediately.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

[[ "$(id -u)" -eq 0 ]] || { echo "Run as root." >&2; exit 1; }

UPLINK="$(ip -4 route show default | awk 'NR == 1 { print $5 }')"
[[ -n "${UPLINK}" ]] || { echo "No IPv4 default-route interface found." >&2; exit 1; }

if ! grep -qF 'source /etc/network/interfaces.d/*' /etc/network/interfaces; then
  echo "ERROR: /etc/network/interfaces does not source interfaces.d; refusing to change networking." >&2
  exit 1
fi

install -d -m 755 /etc/network/interfaces.d /etc/dnsmasq.d /usr/local/lib/autolab

cat > /etc/network/interfaces.d/autolab-private-vm-network <<EOF
auto ${BRIDGE}
iface ${BRIDGE} inet static
    address ${ADDRESS}
    bridge-ports none
    bridge-stp off
    bridge-fd 0
EOF

cat > /etc/dnsmasq.d/autolab-private-vm-network.conf <<EOF
interface=${BRIDGE}
bind-dynamic
dhcp-range=${DHCP_START},${DHCP_END},255.255.255.0,12h
dhcp-option=option:router,${ADDRESS%/*}
dhcp-option=option:dns-server,${DNS_SERVERS}
EOF

cat > /etc/sysctl.d/99-autolab-private-vm-network.conf <<'EOF'
net.ipv4.ip_forward=1
EOF

cat > /usr/local/lib/autolab/private-vm-network-firewall.sh <<EOF
#!/bin/bash
set -euo pipefail
action="\${1:?start or stop required}"
rule() {
  local table="\$1"; shift
  if [[ "\${action}" == start ]]; then
    iptables -t "\${table}" -C "\$@" 2>/dev/null || iptables -t "\${table}" -A "\$@"
  else
    iptables -t "\${table}" -D "\$@" 2>/dev/null || true
  fi
}
rule nat POSTROUTING -s ${SUBNET} -o ${UPLINK} -j MASQUERADE
rule filter FORWARD -i ${BRIDGE} -o ${UPLINK} -j ACCEPT
rule filter FORWARD -i ${UPLINK} -o ${BRIDGE} -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
EOF
chmod 755 /usr/local/lib/autolab/private-vm-network-firewall.sh

cat > /etc/systemd/system/autolab-private-vm-network.service <<'EOF'
[Unit]
Description=Autolab private VM NAT rules
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/lib/autolab/private-vm-network-firewall.sh start
ExecStop=/usr/local/lib/autolab/private-vm-network-firewall.sh stop

[Install]
WantedBy=multi-user.target
EOF

apt-get update -qq
apt-get install -y dnsmasq
sysctl --system >/dev/null
systemctl daemon-reload
systemctl enable autolab-private-vm-network.service

if [[ "${APPLY}" -eq 1 ]]; then
  ip link show "${BRIDGE}" >/dev/null 2>&1 || ifup "${BRIDGE}"
  systemctl restart autolab-private-vm-network.service
  systemctl restart dnsmasq
fi

echo "Private VM network configured: ${BRIDGE} (${ADDRESS}), NAT via ${UPLINK}."
if [[ "${APPLY}" -eq 1 ]]; then
  echo "Private VM network is active."
else
  echo "Run again with --apply to activate it now."
fi
