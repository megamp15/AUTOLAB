#!/bin/bash
# test_resolve-proxmox-node.sh — Self-check for resolve-proxmox-node.sh.
#
# Asserts the contract every workflow depends on:
#   (a) a Stack's node.auto.tfvars resolves to its name and key
#   (b) --node gives the same shape without a file
#   (c) a missing file, an unset name, or an invalid name fails loudly
#   (d) the committed Stacks all resolve
#
# Usage: bash scripts/test_resolve-proxmox-node.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT_UNDER_TEST="$SCRIPT_DIR/resolve-proxmox-node.sh"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

PASS=0
FAIL=0

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    printf 'FAIL: %s\n  expected: %q\n  actual:   %q\n' "$desc" "$expected" "$actual"
  fi
}

assert_fails() {
  local desc="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    FAIL=$((FAIL + 1))
    printf 'FAIL: %s (exited 0)\n' "$desc"
  else
    PASS=$((PASS + 1))
  fi
}

# (a) a Stack
mkdir -p "$TEST_TMP/stack"
printf '# comment\nproxmox_node_name = "xps-pve"\n' > "$TEST_TMP/stack/node.auto.tfvars"
assert_eq "stack resolves" $'name=xps-pve\nkey=XPS_PVE' \
  "$(bash "$SCRIPT_UNDER_TEST" --stack "$TEST_TMP/stack")"

# (b) a node named directly
assert_eq "node resolves" $'name=pve\nkey=PVE' "$(bash "$SCRIPT_UNDER_TEST" --node pve)"

# (c) failures
assert_fails "missing file" bash "$SCRIPT_UNDER_TEST" --stack "$TEST_TMP/nowhere"
printf 'something_else = "x"\n' > "$TEST_TMP/stack/node.auto.tfvars"
assert_fails "unset name" bash "$SCRIPT_UNDER_TEST" --stack "$TEST_TMP/stack"
assert_fails "invalid name" bash "$SCRIPT_UNDER_TEST" --node "-bad"
assert_fails "name with a dot" bash "$SCRIPT_UNDER_TEST" --node "pve.example"
assert_fails "no arguments" bash "$SCRIPT_UNDER_TEST"

# (d) every committed Stack that has a node file
for dir in "$REPO_ROOT"/infra/stacks/*/; do
  [[ -f "$dir/node.auto.tfvars" ]] || continue
  if bash "$SCRIPT_UNDER_TEST" --stack "$dir" >/dev/null; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    printf 'FAIL: committed stack %s does not resolve\n' "$dir"
  fi
done

printf '%d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
