#!/usr/bin/env bats
# Tests for scripts/lib/retry.sh
#
# Uses temp fake tofu / sleep on PATH / overrides so tests do not require
# OpenTofu and run without actual delays.

bats_require_minimum_version 1.5.0

load test_helper

setup_file() {
  export TMPDIR
  TMPDIR="$(mktemp -d "${BATS_FILE_TMPDIR}/retry-test.XXXXXX")"

  # Resolve to scripts/lib/ from the test file location.
  # BATS_TEST_FILENAME is the full path to this .bats file.
  export SCRIPTS_LIB_DIR
  SCRIPTS_LIB_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../../../../scripts/lib" && pwd)"
}

teardown_file() {
  rm -rf "${TMPDIR}"
}

# ── success first try ─────────────────────────────────────────────────────

@test "retry_loop succeeds on first try" {
  source "${SCRIPTS_LIB_DIR}/retry.sh"

  retry_init 3 1
  retry_loop true

  retry_succeeded
  [ "$(retry_count)" -eq 0 ]
}

# ── retry then succeed ────────────────────────────────────────────────────

@test "retry_loop retries then succeeds" {
  source "${SCRIPTS_LIB_DIR}/retry.sh"

  # Create a mock tofu binary on PATH (via setup_bindir) that fails
  # twice then succeeds.
  setup_bindir
  local counter_file="${TMPDIR}/tofu_counter"
  echo "0" > "$counter_file"

  cat > "${TEST_BINDIR}/tofu" << 'TOFU_MOCK'
#!/bin/bash
counter_file="${TMPDIR}/tofu_counter"
count="$(cat "$counter_file")"
count=$((count + 1))
echo "$count" > "$counter_file"
# Fail on first 2 calls (count 1, 2), succeed on 3rd (count 3)
[ "$count" -ge 3 ]
TOFU_MOCK
  chmod +x "${TEST_BINDIR}/tofu"

  retry_init 3 1
  # Override sleep to be a no-op (bypass builtin precedence)
  sleep() { true; }
  retry_loop tofu

  retry_succeeded
  [ "$(retry_count)" -eq 2 ]
}

# ── exhaustion ────────────────────────────────────────────────────────────

@test "retry_loop exhausts all retries" {
  source "${SCRIPTS_LIB_DIR}/retry.sh"

  setup_bindir
  cat > "${TEST_BINDIR}/tofu" << 'TOFU_MOCK'
#!/bin/bash
exit 1
TOFU_MOCK
  chmod +x "${TEST_BINDIR}/tofu"

  retry_init 3 1
  sleep() { true; }

  ! retry_loop tofu

  ! retry_succeeded
  [ "$(retry_count)" -eq 3 ]
}

# ── delay invocation ──────────────────────────────────────────────────────

@test "retry_loop invokes sleep with correct delay between retries" {
  source "${SCRIPTS_LIB_DIR}/retry.sh"

  local sleep_log="${TMPDIR}/sleep_calls"
  : > "$sleep_log"

  # Override sleep to record its argument instead of actually sleeping
  sleep() {
    echo "sleep:$1" >> "$sleep_log"
  }

  retry_init 3 42
  ! retry_loop false

  # Expect two sleeps (after 1st and 2nd failures; 3rd failure exits loop)
  [ "$(wc -l < "$sleep_log")" -eq 2 ]
  while IFS= read -r line; do
    [ "$line" = "sleep:42" ]
  done < "$sleep_log"
}
