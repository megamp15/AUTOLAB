# Shared helpers for env files and wpa_supplicant (source from other scripts).

# Append one key=value line with shell-safe quoting.
env_file_set() {
  local file="$1" key="$2" value="$3"
  local tmp
  tmp="$(mktemp)"
  if [[ -f "${file}" ]]; then
    grep -v "^${key}=" "${file}" > "${tmp}" || true
  fi
  printf '%s=%q\n' "${key}" "${value}" >> "${tmp}"
  mv "${tmp}" "${file}"
  chmod 600 "${file}" 2>/dev/null || true
}

# systemd EnvironmentFile + bash source — values must not contain spaces.
write_failover_env() {
  local file="${1:-/etc/default/network-uplink-failover}"
  local v
  for v in "${ETH_USB:-}" "${WIFI}" "${GW}" "${VMBR:-vmbr0}" "${VMBR_IP}"; do
    [[ "${v}" != *" "* ]] || {
      echo "ERROR: failover env values must not contain spaces: ${v}" >&2
      return 1
    }
  done
  cat > "${file}" << EOF
ETH_USB=${ETH_USB:-}
WIFI=${WIFI}
GW=${GW}
VMBR=${VMBR:-vmbr0}
VMBR_IP=${VMBR_IP}
EOF
  chmod 600 "${file}"
}

# Append a WPA network block. Prefer wpa_passphrase (handles quotes/special chars).
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
