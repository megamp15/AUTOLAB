#!/usr/bin/env bats
# Tests for lib/network-env-schema.sh

bats_require_minimum_version 1.5.0

load test_helper

# ── Schema definition ────────────────────────────────────────────────────────

@test "NETWORK_ENV_REQUIRED_KEYS contains expected keys" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"
  [[ " ${NETWORK_ENV_REQUIRED_KEYS[*]} " == *" WIFI "* ]]
  [[ " ${NETWORK_ENV_REQUIRED_KEYS[*]} " == *" GW "* ]]
  [[ " ${NETWORK_ENV_REQUIRED_KEYS[*]} " == *" VMBR_IP "* ]]
  [[ " ${NETWORK_ENV_REQUIRED_KEYS[*]} " == *" WPA_HOME_SSID "* ]]
  [[ " ${NETWORK_ENV_REQUIRED_KEYS[*]} " == *" WPA_HOME_PSK "* ]]
}

@test "NETWORK_ENV_OPTIONAL_KEYS contains expected keys" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"
  [[ " ${NETWORK_ENV_OPTIONAL_KEYS[*]} " == *" ETH_USB "* ]]
  [[ " ${NETWORK_ENV_OPTIONAL_KEYS[*]} " == *" VMBR "* ]]
  [[ " ${NETWORK_ENV_OPTIONAL_KEYS[*]} " == *" WPA_COUNTRY "* ]]
}

@test "NETWORK_ENV_ALL_KEYS preserves schema order" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"
  [[ " ${NETWORK_ENV_ALL_KEYS[*]} " == *" WIFI GW VMBR_IP WPA_HOME_SSID WPA_HOME_PSK ETH_USB VMBR WPA_COUNTRY WPA_HOME_PRIORITY WPA_HOTSPOT_SSID WPA_HOTSPOT_PSK WPA_HOTSPOT_PRIORITY "* ]]
}

@test "NETWORK_ENV_DEFAULTS contains expected defaults" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"
  local found_vmr=0 found_country=0 found_prio=0
  for entry in "${NETWORK_ENV_DEFAULTS[@]}"; do
    [[ "${entry}" == "VMBR=vmbr0" ]] && found_vmr=1
    [[ "${entry}" == "WPA_COUNTRY=US" ]] && found_country=1
    [[ "${entry}" == "WPA_HOME_PRIORITY=10" ]] && found_prio=1
  done
  [[ "${found_vmr}" -eq 1 ]]
  [[ "${found_country}" -eq 1 ]]
  [[ "${found_prio}" -eq 1 ]]
}

@test "apply_network_env_defaults exports generated defaults" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  unset VMBR WPA_COUNTRY WPA_HOME_PRIORITY WPA_HOTSPOT_PRIORITY
  export WIFI="wlp2s0"
  export GW="10.0.0.1"
  export VMBR_IP="10.0.0.5/24"
  export WPA_HOME_SSID="HomeNet"
  export WPA_HOME_PSK="validpassword"

  apply_network_env_defaults
  [[ "${VMBR}" == "vmbr0" ]]
  [[ "${WPA_COUNTRY}" == "US" ]]
  [[ "${WPA_HOME_PRIORITY}" == "10" ]]
  [[ "${WPA_HOTSPOT_PRIORITY}" == "5" ]]
}

# ── validate_env ──────────────────────────────────────────────────────────────

@test "validate_env passes with all required keys set" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  export WIFI="wlp2s0"
  export GW="10.0.0.1"
  export VMBR_IP="10.0.0.5/24"
  export WPA_HOME_SSID="HomeNet"
  export WPA_HOME_PSK="validpassword"

  run validate_env
  [ "$status" -eq 0 ]
}

@test "validate_env fails when required key is missing" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  export WIFI=""
  export GW="10.0.0.1"
  export VMBR_IP="10.0.0.5/24"
  export WPA_HOME_SSID="HomeNet"
  export WPA_HOME_PSK="validpassword"

  run validate_env
  [ "$status" -ne 0 ]
  [[ "$output" == *"WIFI"* ]]
}

@test "validate_env fails when multiple required keys are missing" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  unset WIFI GW VMBR_IP WPA_HOME_SSID WPA_HOME_PSK

  run validate_env
  [ "$status" -ne 0 ]
}

@test "validate_env catches newline in WPA PSK" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  export WIFI="wlp2s0"
  export GW="10.0.0.1"
  export VMBR_IP="10.0.0.5/24"
  export WPA_HOME_SSID="HomeNet"
  export WPA_HOME_PSK=$'password\nwithnewline'

  run validate_env
  [ "$status" -ne 0 ]
  [[ "$output" == *"ERROR"* ]]
}

@test "secret_has_newline detects LF and CR" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  secret_has_newline $'abc\ndef'
  secret_has_newline $'abc\rdef'
  ! secret_has_newline "clean-secret"
}

@test "sanitize_secret strips line breaks" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  run sanitize_secret $'abc\ndef\rghi'
  [ "$status" -ne 0 ]
  [ "$output" = "abcdefghi" ]
}

@test "assert_valid_wifi_secrets validates schema no-newline fields" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  export WPA_HOME_PSK="valid-home-psk"
  export WPA_HOTSPOT_PSK=$'hotspot\npsk'

  run assert_valid_wifi_secrets
  [ "$status" -ne 0 ]
  [[ "$output" == *"WPA_HOTSPOT_PSK"* ]]
}

# ── describe_field ────────────────────────────────────────────────────────────

@test "describe_field returns description for known keys" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  run describe_field "WIFI"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Wi-Fi"* ]]
  [[ "$output" == *"type: string"* ]]

  run describe_field "GW"
  [ "$status" -eq 0 ]
  [[ "$output" == *"gateway"* ]]
  [[ "$output" == *"type: string"* ]]
}

@test "describe_field returns unknown for unknown keys" {
  source "${SCRIPT_DIR}/lib/network-env-schema.sh"

  run describe_field "UNKNOWN_KEY"
  [[ "$output" == *"Unknown"* ]]
}
