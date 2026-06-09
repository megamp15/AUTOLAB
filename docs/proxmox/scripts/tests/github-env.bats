#!/usr/bin/env bats
# Tests for scripts/lib/github-env.sh
#
# Covers:
#   - append_github_env errors when GITHUB_ENV is unset
#   - append_github_env writes correct heredoc format
#   - append_github_env handles multi-line values

bats_require_minimum_version 1.5.0

load test_helper

setup_file() {
  export TMPDIR
  TMPDIR="$(mktemp -d "${BATS_FILE_TMPDIR}/github-env-test.XXXXXX")"

  # Resolve to scripts/lib/ from the test file location.
  export SCRIPTS_LIB_DIR
  SCRIPTS_LIB_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../../../../scripts/lib" && pwd)"
}

teardown_file() {
  rm -rf "${TMPDIR}"
}

# ── GITHUB_ENV unset → error ───────────────────────────────────────────────

@test "append_github_env exits with error when GITHUB_ENV is unset" {
  source "${SCRIPTS_LIB_DIR}/github-env.sh"

  # Ensure GITHUB_ENV is unset for this test
  local save_GITHUB_ENV="${GITHUB_ENV:-}"
  unset GITHUB_ENV

  run append_github_env "MY_VAR" "hello"

  # Restore before asserting (in case teardown needs it)
  export GITHUB_ENV="${save_GITHUB_ENV}"

  [ "$status" -ne 0 ]
  [[ "$output" == *"ERROR: GITHUB_ENV is not set"* ]]
  [[ "$output" == *"MY_VAR"* ]]
}

# ── basic write ────────────────────────────────────────────────────────────

@test "append_github_env writes correct heredoc format" {
  source "${SCRIPTS_LIB_DIR}/github-env.sh"

  export GITHUB_ENV="${TMPDIR}/github_env_output"
  : > "$GITHUB_ENV"

  append_github_env "TF_VAR_proxmox_endpoint" "https://pve.example.com:8006/"

  local content
  content="$(cat "$GITHUB_ENV")"

  # Expected format:
  #   TF_VAR_proxmox_endpoint<<AUTOLAB_ENV
  #   https://pve.example.com:8006/
  #   AUTOLAB_ENV
  echo "$content" | grep -q "^TF_VAR_proxmox_endpoint<<AUTOLAB_ENV$"
  echo "$content" | grep -q "^https://pve\.example\.com:8006/$"
  # Ensure the closing delimiter is present on its own line
  [[ "$(tail -n 1 "$GITHUB_ENV")" == "AUTOLAB_ENV" ]]
}

# ── multi-line value ────────────────────────────────────────────────────────

@test "append_github_env handles multi-line values" {
  source "${SCRIPTS_LIB_DIR}/github-env.sh"

  export GITHUB_ENV="${TMPDIR}/github_env_multiline"
  : > "$GITHUB_ENV"

  local multiline="line one
line two
line three"

  append_github_env "MULTI_VAR" "$multiline"

  local content
  content="$(cat "$GITHUB_ENV")"

  echo "$content" | grep -q "^MULTI_VAR<<AUTOLAB_ENV$"
  echo "$content" | grep -q "^line one$"
  echo "$content" | grep -q "^line two$"
  echo "$content" | grep -q "^line three$"
  [[ "$(tail -n 1 "$GITHUB_ENV")" == "AUTOLAB_ENV" ]]
}

# ── multiple calls append ───────────────────────────────────────────────────

@test "append_github_env appends to existing GITHUB_ENV content" {
  source "${SCRIPTS_LIB_DIR}/github-env.sh"

  export GITHUB_ENV="${TMPDIR}/github_env_append"
  echo "PREEXISTING=value" > "$GITHUB_ENV"

  append_github_env "VAR_A" "hello"
  append_github_env "VAR_B" "world"

  # First line should still be the pre-existing content
  [[ "$(head -n 1 "$GITHUB_ENV")" == "PREEXISTING=value" ]]

  # Both blocks should be present
  local line_count
  line_count="$(wc -l < "$GITHUB_ENV")"
  # 1 pre-existing + (3 per block × 2 blocks) = 7 lines
  [ "$line_count" -eq 7 ]
}
