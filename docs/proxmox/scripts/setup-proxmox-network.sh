#!/bin/bash
# One-shot Proxmox network setup: USB Ethernet bridge + Wi-Fi + automated failover.
# Run on the host as root after editing /etc/default/proxmox-network.env
#
#   cp config/network.env.example /etc/default/proxmox-network.env
#   nano /etc/default/proxmox-network.env
#   bash setup-proxmox-network.sh --dry-run        # preview without changes
#   bash setup-proxmox-network.sh --apply          # apply configs
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/network-env-schema.sh
source "${SCRIPT_DIR}/lib/network-env-schema.sh"
# shellcheck source=lib/detect.sh
source "${SCRIPT_DIR}/lib/detect.sh"
# shellcheck source=lib/env-config.sh
source "${SCRIPT_DIR}/lib/env-config.sh"
# shellcheck source=lib/network-render.sh
source "${SCRIPT_DIR}/lib/network-render.sh"
CONFIG="${CONFIG:-/etc/default/proxmox-network.env}"
APPLY_NETWORK=0
SKIP_APT=0
DRY_RUN=0

usage() {
  sed -n '2,12p' "$0"
  echo ""
  echo "Options:"
  echo "  --config PATH    Env file (default: /etc/default/proxmox-network.env)"
  echo "  --apply          Run 'systemctl restart networking' at the end (may drop SSH)"
  echo "  --skip-apt       Skip apt install (if wpasupplicant already installed)"
  echo "  --dry-run        Print what would be done without making any changes"
  echo "  -h, --help       This help"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --apply) APPLY_NETWORK=1; shift ;;
    --skip-apt) SKIP_APT=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "==> $*"; }

[[ "$(id -u)" -eq 0 ]] || die "Run as root"

if [[ ! -f "${CONFIG}" ]]; then
  die "Missing ${CONFIG}. Copy and edit config first:
  cp ${SCRIPT_DIR}/../config/network.env.example ${CONFIG}
  nano ${CONFIG}"
fi

# shellcheck source=/dev/null
source "${CONFIG}" || die "Could not read ${CONFIG} (check quoting — PSK must use single quotes, no raw newlines)"

apply_network_env_defaults
validate_env "${CONFIG}" || die "Invalid configuration in ${CONFIG}"

ETH_USB="${ETH_USB:-$(detect_iface '^enx')}"
WIFI="${WIFI:-$(detect_iface '^wlp')}"
GW="${GW:?Set GW in ${CONFIG}}"
VMBR_IP="${VMBR_IP:?Set VMBR_IP in ${CONFIG}}"

[[ -n "${WIFI}" ]] || die "No Wi-Fi interface (wlp*) found. Set WIFI= in ${CONFIG}"

log "Using ETH_USB=${ETH_USB:-<not present yet>}"
log "Using WIFI=${WIFI} GW=${GW} VMBR_IP=${VMBR_IP}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  BACKUP_DIR="[dry-run] (no files copied)"
  log "[dry-run] Would backup existing config files to /root/proxmox-network-backup-*/"
else
  BACKUP_DIR="/root/proxmox-network-backup-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "${BACKUP_DIR}"
  for f in /etc/network/interfaces /etc/wpa_supplicant/wpa_supplicant.conf; do
    [[ -f "$f" ]] && cp -a "$f" "${BACKUP_DIR}/" || true
  done
  log "Backup saved under ${BACKUP_DIR}"
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  if [[ "${SKIP_APT}" -eq 0 ]]; then
    log "[dry-run] Would install packages: wpasupplicant wireless-tools"
  fi
else
  if [[ "${SKIP_APT}" -eq 0 ]]; then
    log "Installing packages..."
    apt-get update -qq
    apt-get install -y wpasupplicant wireless-tools
  fi
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "[dry-run] Would write /etc/sysctl.d/99-proxmox-network.conf"
  echo "---[dry-run] /etc/sysctl.d/99-proxmox-network.conf ---"
  render_sysctl_conf
  echo "---[dry-run] End /etc/sysctl.d/99-proxmox-network.conf ---"
else
  log "Writing /etc/sysctl.d/99-proxmox-network.conf"
  render_sysctl_conf > /etc/sysctl.d/99-proxmox-network.conf
  sysctl --system >/dev/null 2>&1 || true
fi

WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
WIFI_EXTRA_LIST="/etc/default/proxmox-wifi-extra.list"
WIFI_EXTRA_LEGACY="/etc/default/proxmox-wifi-extra.conf"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "[dry-run] Would write ${WPA_CONF}"
  echo "---[dry-run] ${WPA_CONF} ---"
  render_wpa_header "${WPA_COUNTRY}"
  echo ""
  append_wpa_network "/dev/stdout" "${WPA_HOME_SSID}" "${WPA_HOME_PSK}" "${WPA_HOME_PRIORITY}"
  if [[ -n "${WPA_HOTSPOT_SSID:-}" && -n "${WPA_HOTSPOT_PSK:-}" ]]; then
    append_wpa_network "/dev/stdout" "${WPA_HOTSPOT_SSID}" "${WPA_HOTSPOT_PSK}" "${WPA_HOTSPOT_PRIORITY}"
  fi
  if [[ -f "${WIFI_EXTRA_LIST}" && -s "${WIFI_EXTRA_LIST}" ]]; then
    echo ""
    echo "# Extra networks from ${WIFI_EXTRA_LIST}:"
    append_extra_wifi_from_list "/dev/stdout" "${WIFI_EXTRA_LIST}"
  elif [[ -f "${WIFI_EXTRA_LEGACY}" && -s "${WIFI_EXTRA_LEGACY}" ]]; then
    echo ""
    echo "# From deprecated ${WIFI_EXTRA_LEGACY}:"
    cat "${WIFI_EXTRA_LEGACY}"
  fi
  echo "---[dry-run] End ${WPA_CONF} ---"
else
  log "Writing ${WPA_CONF}"
  render_wpa_header "${WPA_COUNTRY}" > "${WPA_CONF}"
  append_wpa_network "${WPA_CONF}" "${WPA_HOME_SSID}" "${WPA_HOME_PSK}" "${WPA_HOME_PRIORITY}"
  if [[ -n "${WPA_HOTSPOT_SSID:-}" && -n "${WPA_HOTSPOT_PSK:-}" ]]; then
    append_wpa_network "${WPA_CONF}" "${WPA_HOTSPOT_SSID}" "${WPA_HOTSPOT_PSK}" "${WPA_HOTSPOT_PRIORITY}"
  fi
  if [[ -f "${WIFI_EXTRA_LIST}" && -s "${WIFI_EXTRA_LIST}" ]]; then
    log "Adding extra Wi-Fi networks from ${WIFI_EXTRA_LIST}"
    append_extra_wifi_from_list "${WPA_CONF}" "${WIFI_EXTRA_LIST}"
  elif [[ -f "${WIFI_EXTRA_LEGACY}" && -s "${WIFI_EXTRA_LEGACY}" ]]; then
    log "WARNING: ${WIFI_EXTRA_LEGACY} is deprecated; re-run configure-proxmox-network-env.sh to use ${WIFI_EXTRA_LIST}"
    cat "${WIFI_EXTRA_LEGACY}" >> "${WPA_CONF}"
  fi
  chmod 600 "${WPA_CONF}"
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "[dry-run] Would write /etc/network/interfaces"
  echo "---[dry-run] /etc/network/interfaces ---"
  render_interfaces "${WIFI}" "${ETH_USB}" "${VMBR}" "${VMBR_IP}"
  echo "---[dry-run] End /etc/network/interfaces ---"
else
  log "Writing /etc/network/interfaces"
  render_interfaces "${WIFI}" "${ETH_USB}" "${VMBR}" "${VMBR_IP}" > /etc/network/interfaces
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "[dry-run] Would install failover service:"
  echo "  - Copy failover-logic.sh to /usr/local/lib/proxmox-network/"
  echo "  - Copy network-uplink-failover.sh to /usr/local/bin/"
  echo "  - Write /etc/default/network-uplink-failover env file"
  echo "  - Install + enable network-uplink-failover.service"
  if [[ -n "${ETH_USB}" ]]; then
    log "[dry-run] Would install bridge watch for ${VMBR}:"
    echo "  - Copy vmbr0-watch.sh to /usr/local/bin/"
    echo "  - Install + enable vmbr0-watch.service"
  else
    log "[dry-run] Skipping vmbr0-watch (ETH_USB empty)."
  fi
else
  log "Installing failover and vmbr0-watch..."
  ETH_USB="${ETH_USB:-}" WIFI="${WIFI}" GW="${GW}" VMBR="${VMBR}" VMBR_IP="${VMBR_IP}" \
    bash "${SCRIPT_DIR}/install-network-uplink-failover.sh"

  if [[ -n "${ETH_USB}" ]]; then
    bash "${SCRIPT_DIR}/install-vmbr0-watch.sh"
  else
    log "Skipping vmbr0-watch (ETH_USB empty — set in config when USB NIC is known)."
  fi
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  if [[ "${APPLY_NETWORK}" -eq 1 ]]; then
    log "[dry-run] Would restart networking: systemctl restart networking"
  else
    log "[dry-run] Configs rendered. Use --apply to apply changes."
  fi
else
  if [[ "${APPLY_NETWORK}" -eq 1 ]]; then
    log "Restarting networking (SSH may disconnect briefly)..."
    systemctl restart networking
    sleep 8
  else
    log "Configs written. Reboot or run with --apply to load /etc/network/interfaces."
  fi
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  if [[ -n "${ETH_USB}" ]]; then
    log "[dry-run] Would bring up ${ETH_USB} and attach to bridge ${VMBR}"
  fi
  log "[dry-run] Would run network-uplink-failover.sh --once"
else
  if [[ -n "${ETH_USB}" ]] && ip link show "${ETH_USB}" &>/dev/null; then
    ip link set "${ETH_USB}" up 2>/dev/null || true
    ip link set "${ETH_USB}" master "${VMBR}" 2>/dev/null || true
  fi

  /usr/local/bin/network-uplink-failover.sh --once 2>/dev/null || true
fi

echo ""
echo "========== Done =========="
echo "Config:     ${CONFIG}"
echo "Backup:     ${BACKUP_DIR}"
echo "UI:         https://${VMBR_IP%/*}:8006  (IP follows active uplink)"
echo ""
echo "--- ${VMBR} ---"
ip -br addr show dev "${VMBR}" 2>/dev/null || true
echo "--- ${WIFI} ---"
ip -br addr show dev "${WIFI}" 2>/dev/null || true
echo "--- route ---"
ip route get 8.8.8.8 2>/dev/null || true
echo "--- services ---"
systemctl is-active network-uplink-failover 2>/dev/null || true
systemctl is-active vmbr0-watch 2>/dev/null || echo "vmbr0-watch: not installed (no USB NIC yet)"
echo ""
if [[ -z "${ETH_USB}" ]]; then
  echo "USB Ethernet: not configured. When plugged in, run:"
  echo "  bash ${SCRIPT_DIR}/enable-usb-ethernet.sh"
fi
if [[ "${APPLY_NETWORK}" -eq 0 ]]; then
  echo "Next:  bash ${SCRIPT_DIR}/setup-proxmox-network.sh --apply"
  echo "   or:  reboot"
fi
