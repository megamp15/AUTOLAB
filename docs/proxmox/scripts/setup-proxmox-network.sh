#!/bin/bash
# One-shot Proxmox network setup: USB Ethernet bridge + Wi-Fi + automated failover.
# Run on the host as root after editing /etc/default/proxmox-network.env
#
#   cp config/network.env.example /etc/default/proxmox-network.env
#   nano /etc/default/proxmox-network.env
#   bash setup-proxmox-network.sh --apply
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/network-env-validate.sh
source "${SCRIPT_DIR}/lib/network-env-validate.sh"
# shellcheck source=lib/proxmox-env.sh
source "${SCRIPT_DIR}/lib/proxmox-env.sh"
CONFIG="${CONFIG:-/etc/default/proxmox-network.env}"
APPLY_NETWORK=0
SKIP_APT=0

usage() {
  sed -n '2,12p' "$0"
  echo ""
  echo "Options:"
  echo "  --config PATH    Env file (default: /etc/default/proxmox-network.env)"
  echo "  --apply          Run 'systemctl restart networking' at the end (may drop SSH)"
  echo "  --skip-apt       Skip apt install (if wpasupplicant already installed)"
  echo "  -h, --help       This help"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --apply) APPLY_NETWORK=1; shift ;;
    --skip-apt) SKIP_APT=1; shift ;;
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

assert_valid_wifi_secrets "${CONFIG}" || die "Invalid Wi-Fi password(s) in ${CONFIG}"

detect_iface() {
  local pattern="$1"
  ip -br link 2>/dev/null | awk -v p="$pattern" '$1 ~ p { print $1; exit }'
}

ETH_USB="${ETH_USB:-$(detect_iface '^enx')}"
WIFI="${WIFI:-$(detect_iface '^wlp')}"
GW="${GW:?Set GW in ${CONFIG}}"
VMBR="${VMBR:-vmbr0}"
VMBR_IP="${VMBR_IP:?Set VMBR_IP in ${CONFIG}}"
WPA_COUNTRY="${WPA_COUNTRY:-US}"
WPA_HOME_PRIORITY="${WPA_HOME_PRIORITY:-10}"
WPA_HOTSPOT_PRIORITY="${WPA_HOTSPOT_PRIORITY:-5}"

[[ -n "${WIFI}" ]] || die "No Wi-Fi interface (wlp*) found. Set WIFI= in ${CONFIG}"
[[ -n "${WPA_HOME_SSID:-}" ]] || die "Set WPA_HOME_SSID in ${CONFIG}"
[[ -n "${WPA_HOME_PSK:-}" ]] || die "WPA_HOME_PSK is empty in ${CONFIG} — run configure-proxmox-network-env.sh or set WPA_HOME_PSK='…' in nano ${CONFIG}"

log "Using ETH_USB=${ETH_USB:-<not present yet>}"
log "Using WIFI=${WIFI} GW=${GW} VMBR_IP=${VMBR_IP}"

BACKUP_DIR="/root/proxmox-network-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"
for f in /etc/network/interfaces /etc/wpa_supplicant/wpa_supplicant.conf; do
  [[ -f "$f" ]] && cp -a "$f" "${BACKUP_DIR}/" || true
done
log "Backup saved under ${BACKUP_DIR}"

if [[ "${SKIP_APT}" -eq 0 ]]; then
  log "Installing packages..."
  apt-get update -qq
  apt-get install -y wpasupplicant wireless-tools
fi

log "Writing /etc/sysctl.d/99-proxmox-network.conf"
cat > /etc/sysctl.d/99-proxmox-network.conf << 'EOF'
net.ipv4.conf.all.ignore_routes_with_linkdown=1
EOF
sysctl --system >/dev/null 2>&1 || true

log "Writing /etc/wpa_supplicant/wpa_supplicant.conf"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
cat > "${WPA_CONF}" << EOF
ctrl_interface=/run/wpa_supplicant
update_config=1
country=${WPA_COUNTRY}
EOF

append_wpa_network "${WPA_CONF}" "${WPA_HOME_SSID}" "${WPA_HOME_PSK}" "${WPA_HOME_PRIORITY}"

if [[ -n "${WPA_HOTSPOT_SSID:-}" && -n "${WPA_HOTSPOT_PSK:-}" ]]; then
  append_wpa_network "${WPA_CONF}" "${WPA_HOTSPOT_SSID}" "${WPA_HOTSPOT_PSK}" "${WPA_HOTSPOT_PRIORITY}"
fi

WIFI_EXTRA_LIST="/etc/default/proxmox-wifi-extra.list"
WIFI_EXTRA_LEGACY="/etc/default/proxmox-wifi-extra.conf"
if [[ -f "${WIFI_EXTRA_LIST}" && -s "${WIFI_EXTRA_LIST}" ]]; then
  log "Adding extra Wi-Fi networks from ${WIFI_EXTRA_LIST}"
  append_extra_wifi_from_list "${WPA_CONF}" "${WIFI_EXTRA_LIST}"
elif [[ -f "${WIFI_EXTRA_LEGACY}" && -s "${WIFI_EXTRA_LEGACY}" ]]; then
  log "WARNING: ${WIFI_EXTRA_LEGACY} is deprecated; re-run configure-proxmox-network-env.sh to use ${WIFI_EXTRA_LIST}"
  cat "${WIFI_EXTRA_LEGACY}" >> "${WPA_CONF}"
fi
chmod 600 "${WPA_CONF}"

log "Writing /etc/network/interfaces"
cat > /etc/network/interfaces << EOF
auto lo
iface lo inet loopback

auto ${WIFI}
iface ${WIFI} inet dhcp
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

EOF

if [[ -n "${ETH_USB}" ]]; then
  cat >> /etc/network/interfaces << EOF
iface ${ETH_USB} inet manual

auto ${VMBR}
iface ${VMBR} inet static
        address ${VMBR_IP}
        bridge-ports ${ETH_USB}
        bridge-stp off
        bridge-fd 0

EOF
else
  log "No USB Ethernet (enx*) now — creating ${VMBR} with bridge-ports none (Wi-Fi-only until USB is added)."
  cat >> /etc/network/interfaces << EOF
auto ${VMBR}
iface ${VMBR} inet static
        address ${VMBR_IP}
        bridge-ports none
        bridge-stp off
        bridge-fd 0

EOF
fi

echo "source /etc/network/interfaces.d/*" >> /etc/network/interfaces

log "Installing failover and vmbr0-watch..."
ETH_USB="${ETH_USB:-}" WIFI="${WIFI}" GW="${GW}" VMBR_IP="${VMBR_IP}" \
  bash "${SCRIPT_DIR}/install-network-uplink-failover.sh"

if [[ -n "${ETH_USB}" ]]; then
  ETH_USB="${ETH_USB}" bash "${SCRIPT_DIR}/install-vmbr0-watch.sh"
else
  log "Skipping vmbr0-watch (ETH_USB empty — set in config when USB NIC is known)."
fi

if [[ "${APPLY_NETWORK}" -eq 1 ]]; then
  log "Restarting networking (SSH may disconnect briefly)..."
  systemctl restart networking
  sleep 8
else
  log "Configs written. Reboot or run with --apply to load /etc/network/interfaces."
fi

if [[ -n "${ETH_USB}" ]] && ip link show "${ETH_USB}" &>/dev/null; then
  ip link set "${ETH_USB}" up 2>/dev/null || true
  ip link set "${ETH_USB}" master "${VMBR}" 2>/dev/null || true
fi

/usr/local/bin/network-uplink-failover.sh --once 2>/dev/null || true

echo ""
echo "========== Done =========="
echo "Config:     ${CONFIG}"
echo "Backup:     ${BACKUP_DIR}"
echo "UI:         https://${VMBR_IP%/*}:8006  (IP follows active uplink)"
echo ""
echo "--- vmbr0 ---"
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
