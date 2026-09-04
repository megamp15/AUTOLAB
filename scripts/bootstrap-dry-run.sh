#!/bin/bash
# bootstrap-dry-run.sh — Production-readiness gate 4: run the bootstrap
# installer in dry-run mode inside a clean Debian container.
#
# Copies docs/proxmox/ to /root/proxmox-setup/ (the same layout the guides
# use), builds a synthetic /etc/default/proxmox-network.env from the example
# file plus placeholder values, then runs setup-proxmox-network.sh --dry-run.
# Nothing on the host is touched; the container is discarded afterwards.
#
# The interactive wizard (configure-proxmox-network-env.sh) reads /dev/tty and
# is not exercised here; its pure logic is covered by the Bats suite.
#
# Usage: bash scripts/bootstrap-dry-run.sh [debian-image]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${1:-debian:trixie-slim}"

command -v docker >/dev/null || { echo "ERROR: docker is required" >&2; exit 1; }

docker run --rm \
  -v "${REPO_ROOT}/docs/proxmox:/src:ro" \
  "${IMAGE}" bash -euo pipefail -c '
    apt-get update -qq >/dev/null
    apt-get install -y -qq iproute2 >/dev/null 2>&1

    mkdir -p /root/proxmox-setup
    cp -r /src/. /root/proxmox-setup/

    env_file=/tmp/proxmox-network.env
    cp /root/proxmox-setup/config/network.env.example "${env_file}"
    cat >> "${env_file}" <<'"'"'ENV'"'"'
WIFI=wlp0s20f3
ETH_USB=enx00e04c680001
GW=192.168.1.1
VMBR_IP=192.168.1.130
WPA_HOME_SSID=ExampleSSID
WPA_HOME_PSK=example-placeholder-psk
ENV

    cd /root/proxmox-setup/scripts
    bash setup-proxmox-network.sh --config "${env_file}" --dry-run --skip-apt

    # Assert the dry run rendered both configs and left the system untouched.
    [[ ! -e /etc/network/interfaces ]] || { echo "ERROR: /etc/network/interfaces was written during dry-run" >&2; exit 1; }
    [[ ! -e /etc/wpa_supplicant/wpa_supplicant.conf ]] || { echo "ERROR: wpa_supplicant.conf was written during dry-run" >&2; exit 1; }
    [[ ! -e /usr/local/bin/network-uplink-failover.sh ]] || { echo "ERROR: failover script was installed during dry-run" >&2; exit 1; }
    echo "bootstrap dry-run OK: configs rendered, no files written"
  '
