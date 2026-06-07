#!/bin/bash
# Install vmbr0-watch on a Proxmox node (run as root).
# The watch script reads ETH_USB and VMBR from /etc/default/network-uplink-failover at runtime,
# so it stays in sync with the network env file without regeneration.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/systemd-units.sh
source "${SCRIPT_DIR}/lib/systemd-units.sh"

install -m 755 "${SCRIPT_DIR}/vmbr0-watch.sh" /usr/local/bin/vmbr0-watch.sh

render_vmbr0_watch_unit | install_unit "vmbr0-watch.service"
