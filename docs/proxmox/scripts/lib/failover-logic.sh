#!/bin/bash
# Network uplink failover logic (source from other scripts).
# Pure functions for Ethernet/Wi-Fi failover: default route + single management IP.
#
# Provides: eth_carrier, bridge_has_eth, prefer_ethernet, iface_has_mgmt_ip,
#           remove_mgmt_ip, add_mgmt_ip, ensure_mgmt_on, wifi_has_ipv4,
#           ensure_wifi_up, apply_routes, apply_state
#
# Expected environment variables (set by caller before calling apply_* functions):
#   ETH_USB   — USB Ethernet interface name (may be empty)
#   WIFI      — Wi-Fi interface name
#   GW        — Default gateway IP
#   VMBR      — Bridge name (default: vmbr0)
#   VMBR_IP   — Management IP/CIDR
#   MGMT_IP   — Management IP without CIDR (derived from VMBR_IP)

# Interface detection lives in detect.sh. The failover daemon installs/sources
# lib files together, so this module depends on the shared detector instead of
# carrying a duplicate implementation.
# shellcheck source=detect.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/detect.sh"

# Backward-compatible alias for callers/tests that used the old local name.
failover_detect_iface() {
  detect_iface "$@"
}

# Check if the USB Ethernet interface has carrier (link detected).
eth_carrier() {
  [[ -n "${ETH_USB:-}" && -d "/sys/class/net/${ETH_USB}" ]] || return 1
  [[ "$(cat "/sys/class/net/${ETH_USB}/carrier" 2>/dev/null || echo 0)" == "1" ]]
}

# Check if the USB Ethernet interface is enslaved to the bridge.
bridge_has_eth() {
  [[ -n "${ETH_USB:-}" ]] || return 1
  bridge link show 2>/dev/null | grep -q "${ETH_USB}"
}

# Return true if Ethernet should be preferred (has carrier and is on bridge).
prefer_ethernet() {
  eth_carrier && bridge_has_eth
}

# Check if an interface has the management IP assigned.
iface_has_mgmt_ip() {
  local iface="$1"
  ip -4 addr show dev "$iface" 2>/dev/null | awk '{print $2}' | grep -q "^${MGMT_IP:-}/"
}

# Remove the management IP from an interface.
remove_mgmt_ip() {
  local iface="$1"
  ip addr del "${VMBR_IP}" dev "$iface" 2>/dev/null || true
}

# Add the management IP to an interface.
add_mgmt_ip() {
  local iface="$1"
  ip addr add "${VMBR_IP}" dev "$iface" 2>/dev/null || true
}

# Ensure the management IP is on the target interface, removing it from others.
ensure_mgmt_on() {
  local target="$1"
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

# Check if the Wi-Fi interface has an IPv4 address.
wifi_has_ipv4() {
  ip -4 addr show dev "${WIFI}" 2>/dev/null | grep -q 'inet '
}

# Bring Wi-Fi interface up and attempt reconnection.
ensure_wifi_up() {
  ip link set "${WIFI}" up 2>/dev/null || true
  if command -v wpa_cli >/dev/null 2>&1; then
    wpa_cli -i "${WIFI}" reconnect 2>/dev/null || true
  fi
}

# Apply default routes based on current uplink state.
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

# Apply the full failover state: management IP + routes.
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
