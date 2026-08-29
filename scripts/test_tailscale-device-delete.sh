#!/bin/bash
# test_tailscale-device-delete.sh — Self-check for tailscale-device-delete.sh.
#
# Uses a fake curl shim placed first on PATH that serves canned responses and
# records every call. Asserts the script's contract branches:
#   (a) 0 matches        -> exit 0
#   (b) 1..n matches     -> DELETE called once per match
#   (c) 404 on delete    -> success
#   (d) persistent 500   -> retries, then exits nonzero
#
# Usage: bash scripts/test_tailscale-device-delete.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$SCRIPT_DIR/tailscale-device-delete.sh"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

FAKE_BIN="$TEST_TMP/bin"
CALL_LOG="$TEST_TMP/curl-calls.log"
mkdir -p "$FAKE_BIN"
export CALL_LOG TEST_TMP

PASS=0
FAIL=0

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    PASS=$((PASS + 1))
    echo "ok: $desc"
  else
    FAIL=$((FAIL + 1))
    echo "FAIL: $desc (expected '$expected', got '$actual')" >&2
  fi
}

# fake curl: reads scenario from $SCENARIO_FILE, logs every invocation.
# Both vars must be exported so this child process can see them.
cat > "$FAKE_BIN/curl" << 'SHIM'
#!/bin/bash
echo "curl $*" >> "$CALL_LOG"

args=("$@")

# Token exchange request?
is_token=0
for a in "${args[@]}"; do [[ "$a" == */oauth/token ]] && is_token=1; done

if [[ $is_token -eq 1 ]]; then
  if [[ "$(python3 -c "import json; print(json.load(open('$SCENARIO_FILE'))['token_status'])")" == "fail" ]]; then
    exit 7
  fi
  echo '{"access_token":"fake-token"}'
  exit 0
fi

# Device list request?
is_list=0
for a in "${args[@]}"; do [[ "$a" == */tailnet/-/devices ]] && is_list=1; done
if [[ $is_list -eq 1 ]]; then
  python3 -c "import json; print(json.dumps(json.load(open('$SCENARIO_FILE'))['devices_response']))"
  exit 0
fi

# DELETE request: extract device id from the URL, look up its status.
id=""
for a in "${args[@]}"; do [[ "$a" == */device/* ]] && id="${a##*/device/}"; done
status="$(python3 -c "
import json
s = json.load(open('$SCENARIO_FILE'))['delete_statuses']
print(s.get('$id', s.get('*', 204)))
")"
case "$status" in
  500)
    # Fail only the first N attempts per id, then succeed (or keep failing).
    count_file="$TEST_TMP/count-$id"
    count="$(cat "$count_file" 2>/dev/null || echo 0)"
    echo $((count + 1)) > "$count_file"
    limit="$(python3 -c "import json; print(json.load(open('$SCENARIO_FILE')).get('fail_500_times', 999))")"
    if [[ "$count" -lt "$limit" ]]; then
      echo "simulated network error" >&2
      exit 7
    fi
    echo 204
    ;;
  *) echo "$status" ;;
esac
exit 0
SHIM
chmod +x "$FAKE_BIN/curl"

# Runs the script under test; always returns 0 so set -e doesn't kill us.
# The script's real exit code lands in $RUN_RC.
RUN_RC=0
run_scenario() {
  local name="$1"
  RUN_RC=0
  export SCENARIO_FILE="$TEST_TMP/$name.json"
  PATH="$FAKE_BIN:$PATH" \
    TAILSCALE_OAUTH_CLIENT_ID=test-id \
    TAILSCALE_OAUTH_CLIENT_SECRET=test-secret \
    bash "$SCRIPT_UNDER_TEST" lab-01 >"$TEST_TMP/out.log" 2>&1 || RUN_RC=$?
}

# --- (a) zero matches -> exit 0 ---
cat > "$TEST_TMP/no-match.json" << 'EOF'
{"token_status": "ok",
 "devices_response": {"devices": [
   {"id": "9", "name": "other-host.tailnet.ts.net", "tags": ["tag:autolab-vm"]},
   {"id": "8", "name": "lab-01.tailnet.ts.net", "tags": ["tag:something-else"]}
 ]}}
EOF
run_scenario no-match
assert_eq "0 matches exits 0" "0" "$RUN_RC"
assert_eq "0 matches issues no DELETEs" "0" "$(grep -c 'DELETE' "$CALL_LOG" || true)"

# --- (b) single + multiple matches -> one DELETE per match ---
rm -f "$CALL_LOG"
cat > "$TEST_TMP/multi-match.json" << 'EOF'
{"token_status": "ok",
 "delete_statuses": {},
 "devices_response": {"devices": [
   {"id": "1", "name": "lab-01.tailnet.ts.net", "tags": ["tag:autolab-vm"]},
   {"id": "2", "name": "lab-01.other.ts.net", "tags": ["tag:autolab-vm"]},
   {"id": "7", "name": "lab-01-1.tailnet.ts.net", "tags": ["tag:autolab-vm"]},
   {"id": "3", "name": "lab-01x.tailnet.ts.net", "tags": ["tag:autolab-vm"]},
   {"id": "6", "name": "123.tailnet.ts.net", "tags": ["tag:autolab-vm"]},
   {"id": "4", "name": "lab-01.no-tag.ts.net", "tags": []}
 ]}}
EOF
run_scenario multi-match
assert_eq "multiple matches exit 0" "0" "$RUN_RC"
# ids 1 and 2 match exactly, and 7 has Tailscale's collision suffix
# (3 is a substring trap, 6 is unrelated and numeric, 4 lacks the tag).
assert_eq "DELETE called once per match" "3" "$(grep -c 'DELETE' "$CALL_LOG")"
assert_eq "matched device 1 deleted" "1" "$(grep -c 'device/1$' "$CALL_LOG")"
assert_eq "matched device 2 deleted" "1" "$(grep -c 'device/2$' "$CALL_LOG")"
assert_eq "matched suffixed device deleted" "1" "$(grep -c 'device/7$' "$CALL_LOG")"

# --- (c) 404 on delete counts as success ---
rm -f "$CALL_LOG"
cat > "$TEST_TMP/gone.json" << 'EOF'
{"token_status": "ok",
 "delete_statuses": {"*": 404},
 "devices_response": {"devices": [
   {"id": "5", "name": "lab-01.tailnet.ts.net", "tags": ["tag:autolab-vm"]}
 ]}}
EOF
run_scenario gone
assert_eq "404 on delete exits 0" "0" "$RUN_RC"

# --- (d) persistent 500 -> retries then nonzero exit ---
rm -f "$CALL_LOG"
cat > "$TEST_TMP/persistent-500.json" << 'EOF'
{"token_status": "ok",
 "fail_500_times": 999,
 "delete_statuses": {"*": 500},
 "devices_response": {"devices": [
   {"id": "6", "name": "lab-01.tailnet.ts.net", "tags": ["tag:autolab-vm"]}
 ]}}
EOF
run_scenario persistent-500
assert_eq "persistent 500 exits nonzero" "1" "$RUN_RC"
# 3 attempts total for the single matching device
assert_eq "retries 3 times before giving up" "3" "$(grep -c 'device/6$' "$CALL_LOG")"

# --- missing env vars -> loud failure ---
if env -u TAILSCALE_OAUTH_CLIENT_ID PATH="$FAKE_BIN:$PATH" \
    bash "$SCRIPT_UNDER_TEST" lab-01 >/dev/null 2>&1; then
  assert_eq "missing creds rejected" "nonzero" "zero"
else
  assert_eq "missing creds rejected" "nonzero" "nonzero"
fi

echo ""
echo "passed: $PASS, failed: $FAIL"
[[ "$FAIL" -eq 0 ]]
