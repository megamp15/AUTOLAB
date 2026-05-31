# Shared checks for /etc/default/proxmox-network.env (source from other scripts).
# Wi-Fi PSKs must not contain newlines — they break `source` and WPA auth.

secret_has_newline() {
  local s="$1"
  [[ "${s}" == *$'\n'* || "${s}" == *$'\r'* ]]
}

# Print sanitized value to stdout; return 1 if anything was stripped.
sanitize_secret() {
  local s="$1"
  local clean="${s}"
  clean="${clean//$'\r'/}"
  clean="${clean//$'\n'/}"
  printf '%s' "${clean}"
  [[ "${s}" == "${clean}" ]]
}

_check_psk_no_newline() {
  local name="$1"
  local value="$2"
  local config="$3"
  [[ -n "${value}" ]] || return 0
  if secret_has_newline "${value}"; then
    echo "ERROR: ${name} in ${config} contains a newline (often shows as \$'\\n…' in the file)." >&2
    echo "  Fix: re-run configure-proxmox-network-env.sh, or edit ${config} and use:" >&2
    echo "    ${name}='your-password-here'" >&2
    echo "  (type password once at the hidden prompt, then Enter — no blank line first)" >&2
    return 1
  fi
  return 0
}

assert_valid_wifi_secrets() {
  local config="${1:-/etc/default/proxmox-network.env}"
  _check_psk_no_newline WPA_HOME_PSK "${WPA_HOME_PSK:-}" "${config}" || return 1
  _check_psk_no_newline WPA_HOTSPOT_PSK "${WPA_HOTSPOT_PSK:-}" "${config}" || return 1
  return 0
}
