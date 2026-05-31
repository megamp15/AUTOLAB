#!/bin/bash
# Ethernet (vmbr0 / USB) vs Wi-Fi failover: default route + single management IP.
# Installed to /usr/local/bin/ by setup-proxmox-network.sh or install-network-uplink-failover.sh
set -euo pipefail

[[ -f /etc/default/network-uplink-failover ]] && source /etc/default/network-uplink-failover

ETH_USB="${ETH_USB:-}"
WIFI="${WIFI:-}"
GW="${GW:-}"
VMBR="${VMBR:-vmbr0}"
VMBR_IP="${VMBR_IP:-}"
MGMT_IP="${VMBR_IP%/*}"

[[ -n "${GW}" && -n "${VMBR_IP}" && -n "${WIFI}" ]] \
  || { echo "Missing GW, VMBR_IP, or WIFI in /etc/default/network-uplink-failover" >&2; exit 1; }

eth_carrier() {
  [[ -n "${ETH_USB}" && -d "/sys/class/net/${ETH_USB}" ]] || return 1
  [[ "$(cat "/sys/class/net/${ETH_USB}/carrier" 2>/dev/null || echo 0)" == "1" ]]
}

bridge_has_eth() {
  [[ -n "${ETH_USB}" ]] || return 1
  bridge link show 2>/dev/null | grep -q "${ETH_USB}"
}

prefer_ethernet() {
  eth_carrier && bridge_has_eth
}

iface_has_mgmt_ip() {
  ip -4 addr show dev "$1" 2>/dev/null | awk '{print $2}' | grep -q "^${MGMT_IP}/"
}

remove_mgmt_ip() {
  ip addr del "${VMBR_IP}" dev "$1" 2>/dev/null || true
}

add_mgmt_ip() {
  ip addr add "${VMBR_IP}" dev "$1" 2>/dev/null || true
}

ensure_mgmt_on() {
  local target=$1
  local iface
  for iface in "${VMBR}" "${WIFI}"; do
    if [[ "${iface}" != "${target}" ]]; then
      remove_mgmt_ip "${iface}"
    fi
  done
  if ! iface_has_mgmt_ip "${target}"; then
    add_mgmt_ip "${target}"
  fi
}

wifi_has_ipv4() {
  ip -4 addr show dev "${WIFI}" 2>/dev/null | grep -q 'inet '
}

ensure_wifi_up() {
  ip link set "${WIFI}" up 2>/dev/null || true
  if command -v wpa_cli >/dev/null 2>&1; then
    wpa_cli -i "${WIFI}" reconnect 2>/dev/null || true
  fi
}

apply_routes() {
  if prefer_ethernet; then
    ip route replace default via "${GW}" dev "${VMBR}" metric 100
    ip route replace default via "${GW}" dev "${WIFI}" metric 200 2>/dev/null || true
  else
    ip route del default via "${GW}" dev "${VMBR}" 2>/dev/null || true
    if wifi_has_ipv4; then
      ip route replace default via "${GW}" dev "${WIFI}" metric 100
    fi
  fi
}

apply_state() {
  if prefer_ethernet; then
    ensure_mgmt_on "${VMBR}"
    dhclient -r "${WIFI}" 2>/dev/null || true
    remove_mgmt_ip "${WIFI}"
    apply_routes
  else
    ensure_wifi_up
    ensure_mgmt_on "${WIFI}"
    apply_routes
  fi
}

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
