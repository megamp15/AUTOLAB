#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load test_helper

@test "check-schema-drift.sh runs all generator checks" {
  run bash "${SCRIPT_DIR}/../../../scripts/check-schema-drift.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Connection adapter drift"* ]]
  [[ "$output" == *"Network env adapter drift"* ]]
  [[ "$output" == *"R2 config drift"* ]]
  [[ "$output" == *"Schema drift checks passed."* ]]
}
