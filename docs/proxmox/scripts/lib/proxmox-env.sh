#!/bin/bash
# Compatibility shim — sources the new focused library modules.
# Existing scripts that source lib/proxmox-env.sh will continue to work.
# New scripts should source the specific modules they need directly.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/env-config.sh
source "${SCRIPT_DIR}/env-config.sh"
# shellcheck source=lib/network-render.sh
source "${SCRIPT_DIR}/network-render.sh"