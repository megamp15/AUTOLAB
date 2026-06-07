#!/bin/bash
# retry.sh — Reusable retry loop for shell commands
#
# Interface:
#   retry_init [max_retries] [retry_delay]
#     Initialise retry state. Defaults: max_retries=3, retry_delay=30.
#
#   retry_loop <command...>
#     Run *command* with retries.  Returns 0 if the command ever succeeds,
#     1 if all retries are exhausted.  Status messages are printed to stderr.
#
#   retry_count
#     Echo the number of retries consumed (0 if the first attempt succeeded).
#
#   retry_succeeded
#     Returns 0 (true) when the most recent retry_loop ended in success,
#     1 otherwise.
#
# Exit codes from retry_loop:
#   0  command succeeded (possibly after retries)
#   1  all retries exhausted
#
# Examples
# --------
#   source retry.sh
#   retry_init 5 10
#   if retry_loop curl -sf https://example.com; then
#     echo "Success"
#   else
#     echo "Failed after 5 attempts"
#   fi
#
# Bash 3.2 compatible (macOS default /bin/bash).
# shellcheck disable=SC2034,SC2155

# --- initialiser -----------------------------------------------------------
retry_init() {
  RETRY_MAX="${1:-3}"
  RETRY_DELAY="${2:-30}"
  RETRY_COUNT=0
  RETRY_SUCCEEDED=false
}

# --- accessors -------------------------------------------------------------
retry_count()      { echo "$RETRY_COUNT"; }
retry_succeeded()  { [ "$RETRY_SUCCEEDED" = true ]; }

# --- core loop -------------------------------------------------------------
# Run the given command-line with retries.  Arguments are forwarded as-is
# (spaces, globs, quoting are preserved through "$@").
retry_loop() {
  RETRY_SUCCEEDED=false
  RETRY_COUNT=0

  while [ "$RETRY_COUNT" -lt "$RETRY_MAX" ] && [ "$RETRY_SUCCEEDED" = false ]; do
    if [ "$RETRY_COUNT" -gt 0 ]; then
      echo "Retry attempt $RETRY_COUNT of $RETRY_MAX (delay ${RETRY_DELAY}s)..." >&2
      sleep "$RETRY_DELAY"
    fi

    if "$@"; then
      RETRY_SUCCEEDED=true
    else
      RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
  done

  [ "$RETRY_SUCCEEDED" = true ]
}
