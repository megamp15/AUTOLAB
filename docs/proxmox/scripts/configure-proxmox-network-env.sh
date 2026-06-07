#!/bin/bash
# Interactive helper: create /etc/default/proxmox-network.env
# Run on the Proxmox host as root before setup-proxmox-network.sh
set -euo pipefail

OUT="${OUT:-/etc/default/proxmox-network.env}"
WIFI_EXTRA_LIST="/etc/default/proxmox-wifi-extra.list"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/network-env-schema.sh
source "${SCRIPT_DIR}/lib/network-env-schema.sh"
# shellcheck source=lib/detect.sh
source "${SCRIPT_DIR}/lib/detect.sh"
# shellcheck source=lib/env-config.sh
source "${SCRIPT_DIR}/lib/env-config.sh"

DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--dry-run]"
      echo ""
      echo "Interactive helper to create /etc/default/proxmox-network.env"
      echo "  --dry-run  Show what would be written without modifying files"
      exit 0 ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--dry-run]"
      exit 1 ;;
  esac
done

ETH_USB="$(detect_iface '^enx')"
WIFI="$(detect_iface '^wlp')"

[[ -n "${WIFI}" ]] || { echo "No Wi-Fi interface (wlp*) found." >&2; exit 1; }

load_existing_env "${OUT}"
apply_network_env_defaults
GW="${GW:-$(detect_gw)}"
VMBR_SUGGEST="$(suggest_vmbr_ip "${GW}" "${WIFI}")"

DEF_HOME_SSID="${WPA_HOME_SSID:-your_home_ssid}"
DEF_HOME_PSK="${WPA_HOME_PSK:-}"
if secret_has_newline "${DEF_HOME_PSK}"; then
  echo "WARNING: Existing WPA_HOME_PSK had newline(s); will sanitize if you keep it." >&2
  DEF_HOME_PSK="$(sanitize_secret "${DEF_HOME_PSK}")" || true
fi
if secret_has_newline "${WPA_HOTSPOT_PSK:-}"; then
  echo "WARNING: Existing WPA_HOTSPOT_PSK had newline(s); will sanitize if you keep it." >&2
  WPA_HOTSPOT_PSK="$(sanitize_secret "${WPA_HOTSPOT_PSK}")" || true
fi
DEF_COUNTRY="${WPA_COUNTRY}"
DEF_GW="${GW:-192.168.1.1}"
DEF_VMBR="${VMBR_IP:-${VMBR_SUGGEST}}"

echo "=== Proxmox network config helper ==="
echo "Writes: ${OUT}"
echo ""
echo "Detected:"
echo "  ETH_USB=${ETH_USB:-<none — plug USB Ethernet or leave empty>}"
echo "  WIFI=${WIFI}"
echo "  GW=${GW:-<unknown>}"
echo "  VMBR_IP (suggested)=${VMBR_SUGGEST}"
echo ""

CLEAR_EXTRA_WIFI=0
if [[ -f "${OUT}" ]]; then
  read -r -p "Overwrite ${OUT}? [y/N]: " ow </dev/tty
  [[ "${ow,,}" == "y" ]] || { echo "Aborted."; exit 0; }
  if [[ -f "${WIFI_EXTRA_LIST}" && -s "${WIFI_EXTRA_LIST}" ]]; then
    read -r -p "Also clear extra Wi-Fi list (${WIFI_EXTRA_LIST})? [y/N]: " clr </dev/tty
    [[ "${clr,,}" == "y" ]] && CLEAR_EXTRA_WIFI=1
  fi
fi

echo ""
echo "--- Wi-Fi (SSID/password — only values we cannot guess) ---"
prompt_into WPA_COUNTRY "Country code (WPA)" "${DEF_COUNTRY}"
prompt_into WPA_HOME_SSID "Home Wi-Fi SSID" "${DEF_HOME_SSID}"
echo ""
prompt_secret_into WPA_HOME_PSK "Home Wi-Fi password" "${DEF_HOME_PSK}"
prompt_into WPA_HOME_PRIORITY "Home priority (higher = preferred)" "${WPA_HOME_PRIORITY}"

echo ""
read -r -p "Add phone hotspot? [y/N]: " add_hotspot </dev/tty
WPA_HOTSPOT_SSID="${WPA_HOTSPOT_SSID:-}"
WPA_HOTSPOT_PSK="${WPA_HOTSPOT_PSK:-}"
WPA_HOTSPOT_PRIORITY="${WPA_HOTSPOT_PRIORITY}"
if [[ "${add_hotspot,,}" == "y" ]]; then
  prompt_into WPA_HOTSPOT_SSID "Hotspot SSID" "${WPA_HOTSPOT_SSID}"
  echo ""
  prompt_secret_into WPA_HOTSPOT_PSK "Hotspot password" "${WPA_HOTSPOT_PSK}"
  prompt_into WPA_HOTSPOT_PRIORITY "Hotspot priority" "${WPA_HOTSPOT_PRIORITY}"
fi

# More Wi-Fi networks — pipe-separated list (do not use | in SSID).
if [[ "${CLEAR_EXTRA_WIFI}" -eq 1 ]]; then
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "  [dry-run] Would clear ${WIFI_EXTRA_LIST}"
  else
    : > "${WIFI_EXTRA_LIST}"
  fi
fi
while true; do
  read -r -p "Add another Wi-Fi network? [y/N]: " add_wifi </dev/tty
  [[ "${add_wifi,,}" == "y" ]] || break
  extra_ssid="" extra_psk="" extra_prio="5"
  prompt_into extra_ssid "Extra Wi-Fi SSID" ""
  echo ""
  prompt_secret_into extra_psk "Extra Wi-Fi password" ""
  prompt_into extra_prio "Priority (higher = preferred when in range)" "5"
  extra_psk="$(sanitize_secret "${extra_psk}")"
  if [[ "${extra_ssid}" == *"|"* ]]; then
    echo "  SSID cannot contain | — skipped." >&2
    continue
  fi
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "  [dry-run] Would add ${extra_ssid} to ${WIFI_EXTRA_LIST}"
  else
    printf '%s|%s|%s\n' "${extra_ssid}" "${extra_psk}" "${extra_prio}" >> "${WIFI_EXTRA_LIST}"
    chmod 600 "${WIFI_EXTRA_LIST}"
    echo "  Added ${extra_ssid} to ${WIFI_EXTRA_LIST}"
  fi
done

echo ""
echo "--- LAN (press Enter to accept detected values) ---"
prompt_into ETH_USB "USB Ethernet iface (empty = none)" "${ETH_USB:-}"
prompt_into WIFI "Wi-Fi iface" "${WIFI}"
prompt_into GW "Gateway IP" "${DEF_GW}"
prompt_into VMBR "Proxmox bridge name" "${VMBR}"
prompt_into VMBR_IP "Proxmox management IP/CIDR" "${DEF_VMBR}"

WPA_HOME_PSK="$(sanitize_secret "${WPA_HOME_PSK}")"
WPA_HOTSPOT_PSK="$(sanitize_secret "${WPA_HOTSPOT_PSK}")"
validate_env "${OUT}" || exit 1

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo ""
  echo "--- [dry-run] Would write ${OUT} ---"
  echo "# Generated by configure-proxmox-network-env.sh on $(date -Iseconds)"
  for key in "${NETWORK_ENV_ALL_KEYS[@]}"; do
    printf '%s=%q\n' "${key}" "${!key:-}"
  done
  echo "--- [dry-run] End ${OUT} ---"
else
  write_args=()
  for key in "${NETWORK_ENV_ALL_KEYS[@]}"; do
    write_args+=("${key}" "${!key:-}")
  done
  write_env "${OUT}" "${write_args[@]}"
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  if [[ -s "${WIFI_EXTRA_LIST}" ]]; then
    echo ""
    echo "Extra Wi-Fi networks (unchanged): ${WIFI_EXTRA_LIST}"
  fi
  echo ""
  echo "[dry-run] No files were modified. Run without --dry-run to apply."
else
  echo ""
  echo "Saved: ${OUT}"
  ls -la "${OUT}"
  grep -E '^(GW|VMBR_IP|WIFI|ETH_USB|WPA_HOME_SSID)=' "${OUT}"
  echo "(Password line hidden — check with: grep '^WPA_HOME_PSK=' ${OUT})"
  if [[ -s "${WIFI_EXTRA_LIST}" ]]; then
    echo "Extra Wi-Fi networks: ${WIFI_EXTRA_LIST}"
  fi
  if [[ -z "${ETH_USB}" ]]; then
    echo ""
    echo "USB Ethernet not set (Wi-Fi-only for now). After plugging in USB:"
    echo "  bash ${SCRIPT_DIR}/enable-usb-ethernet.sh"
  fi
  echo ""
  echo "Next:"
  echo "  cd ${SCRIPT_DIR}"
  echo "  bash setup-proxmox-network.sh --apply"
fi
