#!/usr/bin/env bats
# Tests for scripts/generate-r2-config.sh and scripts/r2-create-token.sh.

bats_require_minimum_version 1.5.0

load test_helper

# ── r2-create-token.sh: --format text|json ────────────────────────────

@test "r2-create-token.sh --dry-run --format json outputs parseable JSON" {
  run --separate-stderr bash "${SCRIPT_DIR}/../../../scripts/r2-create-token.sh" \
    --api-token "test-token" \
    --account-id "test-account" \
    --bucket-name "test-bucket" \
    --token-name "test-token-name" \
    --dry-run \
    --format json
  [ "$status" -eq 0 ]
  # Must be parseable JSON with both required keys
  echo "$output" | jq -e '.access_key_id' >/dev/null
  echo "$output" | jq -e '.secret_access_key' >/dev/null
}

@test "r2-create-token.sh --dry-run default format produces ACCESS_KEY_ID lines" {
  run --separate-stderr bash "${SCRIPT_DIR}/../../../scripts/r2-create-token.sh" \
    --api-token "test-token" \
    --account-id "test-account" \
    --bucket-name "test-bucket" \
    --token-name "test-token-name" \
    --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"ACCESS_KEY_ID="* ]]
  [[ "$output" == *"SECRET_ACCESS_KEY="* ]]
}

@test "r2-create-token.sh --dry-run --format json dry-run values are <dry-run-*>" {
  run --separate-stderr bash "${SCRIPT_DIR}/../../../scripts/r2-create-token.sh" \
    --api-token "test-token" \
    --account-id "test-account" \
    --bucket-name "test-bucket" \
    --token-name "test-token-name" \
    --dry-run \
    --format json
  [ "$status" -eq 0 ]
  local key secret
  key="$(echo "$output" | jq -r '.access_key_id')"
  secret="$(echo "$output" | jq -r '.secret_access_key')"
  [[ "$key" == "<dry-run-access-key-id>" ]]
  [[ "$secret" == "<dry-run-secret-access-key>" ]]
}

@test "r2-create-token.sh --format invalid exits with error" {
  run --separate-stderr bash "${SCRIPT_DIR}/../../../scripts/r2-create-token.sh" \
    --api-token "test-token" \
    --account-id "test-account" \
    --bucket-name "test-bucket" \
    --token-name "test-token-name" \
    --dry-run \
    --format invalid
  [ "$status" -ne 0 ]
}

@test "setup-r2-backend.sh --dry-run --format json outputs setup result" {
  run --separate-stderr bash "${SCRIPT_DIR}/../../../scripts/setup-r2-backend.sh" \
    --api-token "test-token" \
    --account-id "test-account" \
    --bucket-name "test-bucket" \
    --token-name "test-token-name" \
    --dry-run \
    --format json
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.bucket_name == "test-bucket"' >/dev/null
  echo "$output" | jq -e '.github_environment.secrets.R2_ACCESS_KEY_ID' >/dev/null
  echo "$output" | jq -e '.local_environment.R2_ENDPOINT == "https://test-account.r2.cloudflarestorage.com"' >/dev/null
}

@test "setup-r2-backend.sh --format invalid exits with error" {
  run --separate-stderr bash "${SCRIPT_DIR}/../../../scripts/setup-r2-backend.sh" \
    --api-token "test-token" \
    --account-id "test-account" \
    --bucket-name "test-bucket" \
    --token-name "test-token-name" \
    --dry-run \
    --format invalid
  [ "$status" -ne 0 ]
}

# ── generate-r2-config.sh: --terramate and --defaults flags ──────────

@test "generate-r2-config.sh --check passes (no drift)" {
  run bash "${SCRIPT_DIR}/../../../scripts/generate-r2-config.sh" --check
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* || "$output" == *"matches source"* ]]
}

@test "generate-r2-config.sh --terramate --check only checks terramate" {
  run bash "${SCRIPT_DIR}/../../../scripts/generate-r2-config.sh" --terramate --check
  [ "$status" -eq 0 ]
  [[ "$output" == *"terramate"* || "$output" == *"matches source"* ]]
}

@test "generate-r2-config.sh --defaults --check only checks defaults" {
  run bash "${SCRIPT_DIR}/../../../scripts/generate-r2-config.sh" --defaults --check
  [ "$status" -eq 0 ]
  [[ "$output" == *"r2-defaults"* || "$output" == *"matches source"* ]]
}

@test "generate-r2-config.sh --terramate --check does not mention r2-defaults" {
  run bash "${SCRIPT_DIR}/../../../scripts/generate-r2-config.sh" --terramate --check
  [ "$status" -eq 0 ]
  [[ "$output" != *"r2-defaults"* && "$output" != *"r2_defaults"* ]]
}

@test "generate-r2-config.sh --defaults --check does not mention terramate" {
  run bash "${SCRIPT_DIR}/../../../scripts/generate-r2-config.sh" --defaults --check
  [ "$status" -eq 0 ]
  [[ "$output" != *"terramate"* ]]
}
