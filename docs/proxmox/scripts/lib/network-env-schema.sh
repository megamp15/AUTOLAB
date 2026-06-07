#!/bin/bash
# Network environment schema — AUTO-GENERATED from network-env-schema.yaml
# by scripts/generate-network-env-adapters.sh. Do not edit manually.
#
# Provides: NETWORK_ENV_ALL_KEYS, NETWORK_ENV_REQUIRED_KEYS,
#           NETWORK_ENV_OPTIONAL_KEYS, NETWORK_ENV_DEFAULTS,
#           apply_network_env_defaults, secret_has_newline, sanitize_secret,
#           assert_valid_wifi_secrets, validate_env, validate_field_value,
#           describe_field

# The env file is /etc/default/proxmox-network.env (or a path passed to
# scripts via --config). It is sourced as shell, so values must be shell-safe.
#
# Required keys must be present and non-empty.
# Optional keys have defaults listed in NETWORK_ENV_DEFAULTS.

# All schema keys in declaration order.
NETWORK_ENV_ALL_KEYS=(
  WIFI
  GW
  VMBR_IP
  WPA_HOME_SSID
  WPA_HOME_PSK
  ETH_USB
  VMBR
  WPA_COUNTRY
  WPA_HOME_PRIORITY
  WPA_HOTSPOT_SSID
  WPA_HOTSPOT_PSK
  WPA_HOTSPOT_PRIORITY
)

# Keys that MUST be present and non-empty.
NETWORK_ENV_REQUIRED_KEYS=(
  WIFI
  GW
  VMBR_IP
  WPA_HOME_SSID
  WPA_HOME_PSK
)

# Keys that MAY be absent; defaults are applied by setup scripts.
NETWORK_ENV_OPTIONAL_KEYS=(
  ETH_USB
  VMBR
  WPA_COUNTRY
  WPA_HOME_PRIORITY
  WPA_HOTSPOT_SSID
  WPA_HOTSPOT_PSK
  WPA_HOTSPOT_PRIORITY
)

# Default values for optional keys (key=default pairs).
NETWORK_ENV_DEFAULTS=(
  "VMBR=vmbr0"
  "WPA_COUNTRY=US"
  "WPA_HOME_PRIORITY=10"
  "WPA_HOTSPOT_PRIORITY=5"
)

# Apply generated defaults to unset or empty optional keys.
apply_network_env_defaults() {
  local kv key default
  for kv in "${NETWORK_ENV_DEFAULTS[@]}"; do
    key="${kv%%=*}"
    default="${kv#*=}"
    if [[ -z "${!key:-}" ]]; then
      printf -v "${key}" '%s' "${default}"
      export "${key}"
    fi
  done
}

# ── Validation ───────────────────────────────────────────────────────────────

# Return true when a value contains line breaks that would break env sourcing or WPA auth.
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

# Validate a single field's value against its schema constraints.
# Returns 0 on success, 1 on failure with error message on stderr.
# Usage: validate_field_value FIELD_NAME VALUE
validate_field_value() {
  local key="$1"
  local value="$2"
  case "${key}" in
    WPA_HOME_PSK|WPA_HOTSPOT_PSK)
      if secret_has_newline "${value}"; then
        echo "ERROR: ${key} must not contain newlines" >&2
        return 1
      fi
      ;;
    WPA_HOME_PRIORITY|WPA_HOTSPOT_PRIORITY)
      if [[ -n "${value}" ]] && ! [[ "${value}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ${key} must be a number, got: ${value}" >&2
        return 1
      fi
      ;;
  esac
  return 0
}

# Validate all schema-declared sensitive no-newline fields.
assert_valid_wifi_secrets() {
  local config="${1:-/etc/default/proxmox-network.env}"
  local key value
  key="WPA_HOME_PSK"
  value="${!key:-}"
  if [[ -n "${value}" ]] && secret_has_newline "${value}"; then
    echo "ERROR: ${key} in ${config} contains a newline (often shows as \$'\\n…' in the file)." >&2
    echo "  Fix: re-run configure-proxmox-network-env.sh, or edit ${config} and use single quotes." >&2
    return 1
  fi
  key="WPA_HOTSPOT_PSK"
  value="${!key:-}"
  if [[ -n "${value}" ]] && secret_has_newline "${value}"; then
    echo "ERROR: ${key} in ${config} contains a newline (often shows as \$'\\n…' in the file)." >&2
    echo "  Fix: re-run configure-proxmox-network-env.sh, or edit ${config} and use single quotes." >&2
    return 1
  fi
  return 0
}

# ── validate_env function ──

# Validate that all required keys are present and non-empty, and that all
# set values pass field-level validation (type checks, no-newlines, etc.).
# Returns 0 on success, 1 on failure with error messages on stderr.
#
# Usage:
#   source "${CONFIG}"
#   validate_env || die "Invalid env"
validate_env() {
  local config="${1:-/etc/default/proxmox-network.env}"
  local missing=0
  local key

  for key in "${NETWORK_ENV_REQUIRED_KEYS[@]}"; do
    if [[ -z "${!key:-}" ]]; then
      echo "ERROR: Required key ${key} is missing or empty in ${config}" >&2
      missing=$((missing + 1))
    else
      validate_field_value "${key}" "${!key}" || missing=$((missing + 1))
    fi
  done

  for key in "${NETWORK_ENV_OPTIONAL_KEYS[@]}"; do
    if [[ -n "${!key:-}" ]]; then
      validate_field_value "${key}" "${!key}" || missing=$((missing + 1))
    fi
  done

  if [[ "${missing}" -gt 0 ]]; then
    echo "ERROR: ${missing} validation error(s) in ${config}" >&2
    return 1
  fi
  return 0
}

# ── Key description ──────────────────────────────────────────────────────────

# Print a one-line description of a key (including type).
# Useful for help text and error messages.
describe_field() {
  local key="$1"
  case "${key}" in
    WIFI)                    echo "Wi-Fi interface name (e.g. wlp2s0) [type: string]" ;;
    GW)                      echo "Default gateway IP address [type: string]" ;;
    VMBR_IP)                 echo "Proxmox management IP/CIDR (e.g. 10.0.0.5/24) [type: string]" ;;
    WPA_HOME_SSID)           echo "Home Wi-Fi SSID [type: string]" ;;
    WPA_HOME_PSK)            echo "Home Wi-Fi password (use single quotes in env file) [type: string]" ;;
    ETH_USB)                 echo "USB Ethernet interface name (e.g. enx00e04c123456); empty if not yet plugged in [type: string]" ;;
    VMBR)                    echo "Proxmox bridge name [type: string]" ;;
    WPA_COUNTRY)             echo "WPA country code [type: string]" ;;
    WPA_HOME_PRIORITY)       echo "Home Wi-Fi priority (higher = preferred) [type: number]" ;;
    WPA_HOTSPOT_SSID)        echo "Phone hotspot SSID; optional [type: string]" ;;
    WPA_HOTSPOT_PSK)         echo "Phone hotspot password; optional, use single quotes in env file [type: string]" ;;
    WPA_HOTSPOT_PRIORITY)    echo "Hotspot priority [type: number]" ;;
    *) echo "Unknown key: ${key}" ;;
  esac
}
