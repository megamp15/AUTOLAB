#!/bin/bash
# Interface detection and suggestion helpers (source from other scripts).
# Provides: detect_iface, detect_gw, detect_vmbr_ip, detect_wifi_ip, suggest_vmbr_ip

# Print the first interface matching an awk pattern (e.g. '^enx', '^wlp').
# Returns empty string if nothing matches.
detect_iface() {
  local pattern="$1"
  ip -br link 2>/dev/null | awk -v p="$pattern" '$1 ~ p { print $1; exit }'
}

# Print the default gateway IP.
detect_gw() {
  ip route show default 2>/dev/null | awk '{print $3; exit}'
}

# Print the IPv4 address (with CIDR) of vmbr0, or empty.
detect_vmbr_ip() {
  ip -4 addr show dev vmbr0 2>/dev/null | awk '/inet / { print $2; exit }'
}

# Print the IPv4 address (with CIDR) of a given Wi-Fi interface.
detect_wifi_ip() {
  local wifi="$1"
  ip -4 addr show dev "${wifi}" 2>/dev/null | awk '/inet / { print $2; exit }'
}

# Suggest a management IP for vmbr0 on the same subnet as the gateway.
# Prefers: existing vmbr0 IP > Wi-Fi IP > gateway subnet .130/24 > 192.168.1.100/24.
suggest_vmbr_ip() {
  local gw="$1"
  local wifi="$2"
  local ip

  ip="$(detect_vmbr_ip)"
  if [[ -n "${ip}" ]]; then
    echo "${ip}"
    return
  fi

  ip="$(detect_wifi_ip "${wifi}")"
  if [[ -n "${ip}" ]]; then
    echo "${ip}"
    return
  fi

  if [[ "${gw}" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.[0-9]+$ ]]; then
    echo "${BASH_REMATCH[1]}.130/24"
    return
  fi

  echo "192.168.1.100/24"
}