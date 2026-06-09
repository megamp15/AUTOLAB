# Shared helpers for network library bats tests.
# Usage: load test_helper  (from any test file in this directory)

bats_require_minimum_version 1.5.0

# Resolve SCRIPT_DIR to the parent of tests/ (i.e., docs/proxmox/scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Temp directory ──────────────────────────────────────────────────────────
# TMPDIR is created once per test file and cleaned up after all tests finish.

setup_file() {
  export TMPDIR
  TMPDIR="$(mktemp -d "${BATS_FILE_TMPDIR}/network-test.XXXXXX")"
}

teardown_file() {
  rm -rf "${TMPDIR}"
}

# ── Mock-bin helpers ────────────────────────────────────────────────────────
# Create a temporary bin directory and prepend it to PATH.
# Each call is idempotent within a test process.
setup_bindir() {
  if [[ -z "${TEST_BINDIR:-}" ]]; then
    export TEST_BINDIR
    TEST_BINDIR="$(mktemp -d "${TMPDIR}/bindir.XXXXXX")"
    PATH="${TEST_BINDIR}:${PATH}"
  fi
}

# Mock the ip(8) command.
# The output for each invocation is read from control files:
#   ${TEST_BINDIR}/ip_br_link          ip -br link
#   ${TEST_BINDIR}/ip_route_default    ip route show default
#   ${TEST_BINDIR}/ip_addr_vmbr0       ip -4 addr show dev vmbr0
#   ${TEST_BINDIR}/ip_addr_wlp2s0      ip -4 addr show dev wlp2s0
# Write to these files inside your @test before calling the function under test.
mock_ip() {
  setup_bindir
  cat > "${TEST_BINDIR}/ip" << 'MOCKIP'
#!/bin/bash
MOCKDIR="$(dirname "$0")"
case "$*" in
  "-br link")                     [[ -f "${MOCKDIR}/ip_br_link" ]]        && cat "${MOCKDIR}/ip_br_link"        ;;
  "route show default")           [[ -f "${MOCKDIR}/ip_route_default" ]]  && cat "${MOCKDIR}/ip_route_default"  ;;
  "-4 addr show dev vmbr0")       [[ -f "${MOCKDIR}/ip_addr_vmbr0" ]]     && cat "${MOCKDIR}/ip_addr_vmbr0"     ;;
  "-4 addr show dev wlp2s0")      [[ -f "${MOCKDIR}/ip_addr_wlp2s0" ]]    && cat "${MOCKDIR}/ip_addr_wlp2s0"    ;;
esac
MOCKIP
  chmod +x "${TEST_BINDIR}/ip"
}

# Mock wpa_passphrase(8).
# Outputs a valid WPA network block resembling the real tool's output.
mock_wpa_passphrase() {
  setup_bindir
  cat > "${TEST_BINDIR}/wpa_passphrase" << 'MOCKWPA'
#!/bin/bash
ssid="$1"
psk="$2"
cat << NWBLOCK
network={
    ssid="${ssid}"
    #psk="${psk}"
    psk=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
}
NWBLOCK
MOCKWPA
  chmod +x "${TEST_BINDIR}/wpa_passphrase"
}

# ── PATH manipulation ───────────────────────────────────────────────────────
# Restructure PATH to exclude directories containing a particular command.
# Usage:
#   local old_PATH
#   old_PATH="$(path_without "somecmd")"
#   … test code that relies on somecmd NOT being found …
#   PATH="${old_PATH}"
path_without() {
  local cmd="$1"
  local old_PATH="${PATH}"
  local new_PATH=""
  local dir
  local IFS=':'
  for dir in ${PATH}; do
    if [[ ! -x "${dir}/${cmd}" ]]; then
      new_PATH="${new_PATH:+${new_PATH}:}${dir}"
    fi
  done
  PATH="${new_PATH}"
  echo "${old_PATH}"
}
