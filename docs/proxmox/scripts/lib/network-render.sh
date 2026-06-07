#!/bin/bash
# Network config rendering helpers (source from other scripts).
# Pure functions that render config files from structured inputs.
#
# Provides: render_sysctl_conf, render_wpa_header, append_wpa_network,
#           append_extra_wifi_from_list, render_interfaces

# Render /etc/sysctl.d/99-proxmox-network.conf content to stdout.
render_sysctl_conf() {
  cat << 'EOF'
net.ipv4.conf.all.ignore_routes_with_linkdown=1
EOF
}

# Render the WPA supplicant header (ctrl_interface, update_config, country) to stdout.
# Usage: render_wpa_header "$WPA_COUNTRY"
render_wpa_header() {
  local country="${1:-US}"
  cat << EOF
ctrl_interface=/run/wpa_supplicant
update_config=1
country=${country}
EOF
}

# Append a WPA network block to a config file.
# Prefers wpa_passphrase (handles quotes/special chars) when available.
append_wpa_network() {
  local conf="$1" ssid="$2" psk="$3" priority="$4"
  if command -v wpa_passphrase >/dev/null 2>&1; then
    wpa_passphrase "${ssid}" "${psk}" | sed "\$ s/\}$/    priority=${priority}\n}/" >> "${conf}"
  else
    local essid epsk
    essid="$(printf '%s' "${ssid}" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    epsk="$(printf '%s' "${psk}" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    cat >> "${conf}" << EOF

network={
    ssid="${essid}"
    psk="${epsk}"
    priority=${priority}
}
EOF
  fi
}

# Read /etc/default/proxmox-wifi-extra.list lines: SSID|PSK|priority
# and append each as a WPA network block.
append_extra_wifi_from_list() {
  local conf="$1" list="${2:-/etc/default/proxmox-wifi-extra.list}"
  [[ -f "${list}" && -s "${list}" ]] || return 0
  local line ssid psk prio
  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line}" || "${line}" =~ ^# ]] && continue
    IFS='|' read -r ssid psk prio <<< "${line}"
    [[ -n "${ssid}" && -n "${psk}" ]] || continue
    prio="${prio:-5}"
    append_wpa_network "${conf}" "${ssid}" "${psk}" "${prio}"
  done < "${list}"
}

# Render /etc/network/interfaces content to stdout.
# Usage: render_interfaces "$WIFI" "$ETH_USB" "$VMBR" "$VMBR_IP"
render_interfaces() {
  local wifi="$1" eth_usb="$2" vmbr="$3" vmbr_ip="$4"

  cat << EOF
auto lo
iface lo inet loopback

auto ${wifi}
iface ${wifi} inet dhcp
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

EOF

  if [[ -n "${eth_usb}" ]]; then
    cat << EOF
iface ${eth_usb} inet manual

auto ${vmbr}
iface ${vmbr} inet static
        address ${vmbr_ip}
        bridge-ports ${eth_usb}
        bridge-stp off
        bridge-fd 0

EOF
  else
    cat << EOF
auto ${vmbr}
iface ${vmbr} inet static
        address ${vmbr_ip}
        bridge-ports none
        bridge-stp off
        bridge-fd 0

EOF
  fi

  echo "source /etc/network/interfaces.d/*"
}