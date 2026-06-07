#!/usr/bin/env bats
# Tests for lib/network-render.sh

bats_require_minimum_version 1.5.0

load test_helper

# ── render_sysctl_conf ──────────────────────────────────────────────────────

@test "render_sysctl_conf outputs expected sysctl line" {
  source "${SCRIPT_DIR}/lib/network-render.sh"
  run render_sysctl_conf
  [ "$status" -eq 0 ]
  [[ "$output" == *"net.ipv4.conf.all.ignore_routes_with_linkdown=1"* ]]
}

# ── render_wpa_header ───────────────────────────────────────────────────────

@test "render_wpa_header outputs ctrl_interface, update_config, and country" {
  source "${SCRIPT_DIR}/lib/network-render.sh"
  run render_wpa_header

  [ "$status" -eq 0 ]
  [[ "$output" == *"ctrl_interface=/run/wpa_supplicant"* ]]
  [[ "$output" == *"update_config=1"* ]]
  [[ "$output" == *"country="* ]]
}

@test "render_wpa_header uses custom country" {
  source "${SCRIPT_DIR}/lib/network-render.sh"
  run render_wpa_header "DE"

  [ "$status" -eq 0 ]
  [[ "$output" == *"country=DE"* ]]
}

# ── append_wpa_network ──────────────────────────────────────────────────────

@test "append_wpa_network with wpa_passphrase appends network block with priority" {
  mock_wpa_passphrase
  source "${SCRIPT_DIR}/lib/network-render.sh"

  local tmpfile="${TMPDIR}/wpa_supplicant.conf"
  append_wpa_network "${tmpfile}" "MySSID" "MyPSK" "10"

  # Verify the block was appended
  grep -q 'ssid="MySSID"' "${tmpfile}"
  grep -q 'priority=10' "${tmpfile}"
  grep -q 'network={' "${tmpfile}"
}

@test "append_wpa_network without wpa_passphrase uses fallback path" {
  source "${SCRIPT_DIR}/lib/network-render.sh"

  # Ensure wpa_passphrase is not on PATH so the fallback branch is taken
  local old_PATH
  old_PATH="$(path_without "wpa_passphrase")"

  local tmpfile="${TMPDIR}/wpa_fallback.conf"
  append_wpa_network "${tmpfile}" "FallbackSSID" "FallbackPSK" "5"

  PATH="${old_PATH}"

  # Fallback should generate a valid network block
  grep -q 'ssid="FallbackSSID"' "${tmpfile}"
  grep -q 'psk="FallbackPSK"' "${tmpfile}"
  grep -q 'priority=5' "${tmpfile}"
  grep -q 'network={' "${tmpfile}"
}

# ── append_extra_wifi_from_list ─────────────────────────────────────────────

@test "append_extra_wifi_from_list reads list file and appends networks" {
  mock_wpa_passphrase
  source "${SCRIPT_DIR}/lib/network-render.sh"

  local conf="${TMPDIR}/wpa_extra.conf"
  local list="${TMPDIR}/wifi-extra.list"

  # Create the extra list file
  cat > "${list}" << 'EOF'
# SSID|PSK|priority
HomeNet|homepsk123|10
GuestNet|guestpsk456|5
EOF

  # Touch the conf file so it exists
  touch "${conf}"
  append_extra_wifi_from_list "${conf}" "${list}"

  # Both networks should be appended
  grep -q 'ssid="HomeNet"' "${conf}"
  grep -q 'ssid="GuestNet"' "${conf}"
  grep -q 'priority=10' "${conf}"
  grep -q 'priority=5' "${conf}"
}

# ── render_interfaces ───────────────────────────────────────────────────────

@test "render_interfaces with ETH_USB includes bridge-ports with USB interface" {
  source "${SCRIPT_DIR}/lib/network-render.sh"
  run render_interfaces "wlp2s0" "enx00e04c123456" "vmbr0" "10.0.0.5/24"

  [ "$status" -eq 0 ]
  # Bridge should reference the USB interface
  [[ "$output" == *"bridge-ports enx00e04c123456"* ]]
}

@test "render_interfaces without ETH_USB uses bridge-ports none" {
  source "${SCRIPT_DIR}/lib/network-render.sh"
  run render_interfaces "wlp2s0" "" "vmbr0" "10.0.0.5/24"

  [ "$status" -eq 0 ]
  [[ "$output" == *"bridge-ports none"* ]]
}

@test "render_interfaces includes source directive for interfaces.d" {
  source "${SCRIPT_DIR}/lib/network-render.sh"
  run render_interfaces "wlp2s0" "enx00e04c123456" "vmbr0" "10.0.0.5/24"

  [ "$status" -eq 0 ]
  [[ "$output" == *"source /etc/network/interfaces.d/*"* ]]
}
