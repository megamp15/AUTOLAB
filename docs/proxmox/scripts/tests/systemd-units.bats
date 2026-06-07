#!/usr/bin/env bats
# Tests for lib/systemd-units.sh

bats_require_minimum_version 1.5.0

load test_helper

# ── render_failover_unit ─────────────────────────────────────────────────────

@test "render_failover_unit outputs valid systemd unit with After and Wants" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_failover_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"After=networking.service"* ]]
  [[ "$output" == *"Wants=networking.service"* ]]
}

@test "render_failover_unit includes ExecStart and ExecStartPre" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_failover_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"ExecStartPre=/usr/local/bin/network-uplink-failover.sh --once"* ]]
  [[ "$output" == *"ExecStart=/usr/local/bin/network-uplink-failover.sh"* ]]
}

@test "render_failover_unit includes EnvironmentFile" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_failover_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"EnvironmentFile=-/etc/default/network-uplink-failover"* ]]
}

@test "render_failover_unit includes Restart=always" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_failover_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"Restart=always"* ]]
}

@test "render_failover_unit includes Install section" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_failover_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"WantedBy=multi-user.target"* ]]
}

# ── render_vmbr0_watch_unit ──────────────────────────────────────────────────

@test "render_vmbr0_watch_unit outputs valid systemd unit" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_vmbr0_watch_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"Description=Re-attach USB Ethernet to vmbr0 when replugged"* ]]
}

@test "render_vmbr0_watch_unit includes ExecStart" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_vmbr0_watch_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"ExecStart=/usr/local/bin/vmbr0-watch.sh"* ]]
}

@test "render_vmbr0_watch_unit includes Restart=always" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_vmbr0_watch_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"Restart=always"* ]]
}

@test "render_vmbr0_watch_unit includes Install section" {
  source "${SCRIPT_DIR}/lib/systemd-units.sh"
  run render_vmbr0_watch_unit
  [ "$status" -eq 0 ]
  [[ "$output" == *"WantedBy=multi-user.target"* ]]
}
