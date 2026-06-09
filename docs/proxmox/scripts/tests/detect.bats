#!/usr/bin/env bats
# Tests for lib/detect.sh

bats_require_minimum_version 1.5.0

load test_helper

setup() {
  mock_ip
}

# ── detect_iface ────────────────────────────────────────────────────────────

@test "detect_iface returns first interface matching pattern" {
  cat > "${TEST_BINDIR}/ip_br_link" << 'EOF'
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP>
enx00e04c123456  UP             00:e0:4c:12:34:56 <BROADCAST,MULTICAST,UP,LOWER_UP>
wlp2s0           UP             12:34:56:78:9a:bc <BROADCAST,MULTICAST,UP,LOWER_UP>
EOF
  source "${SCRIPT_DIR}/lib/detect.sh"
  result="$(detect_iface '^enx')"
  [[ "${result}" == "enx00e04c123456" ]]
}

@test "detect_iface returns empty when no interface matches pattern" {
  cat > "${TEST_BINDIR}/ip_br_link" << 'EOF'
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP>
wlp2s0           UP             12:34:56:78:9a:bc <BROADCAST,MULTICAST,UP,LOWER_UP>
EOF
  source "${SCRIPT_DIR}/lib/detect.sh"
  result="$(detect_iface '^enx')"
  [[ -z "${result}" ]]
}

# ── detect_gw ───────────────────────────────────────────────────────────────

@test "detect_gw extracts default gateway" {
  cat > "${TEST_BINDIR}/ip_route_default" << 'EOF'
default via 10.0.0.1 dev enx00e04c123456
EOF
  source "${SCRIPT_DIR}/lib/detect.sh"
  result="$(detect_gw)"
  [[ "${result}" == "10.0.0.1" ]]
}

@test "detect_gw returns empty when no default route exists" {
  # No ip_route_default file → mock ip returns empty output
  source "${SCRIPT_DIR}/lib/detect.sh"
  result="$(detect_gw)"
  [[ -z "${result}" ]]
}

# ── detect_vmbr_ip ──────────────────────────────────────────────────────────

@test "detect_vmbr_ip extracts IPv4 address from vmbr0" {
  cat > "${TEST_BINDIR}/ip_addr_vmbr0" << 'EOF'
2: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    inet 10.0.0.5/24 brd 10.0.0.255 scope global vmbr0
       valid_lft forever preferred_lft forever
EOF
  source "${SCRIPT_DIR}/lib/detect.sh"
  result="$(detect_vmbr_ip)"
  [[ "${result}" == "10.0.0.5/24" ]]
}

# ── detect_wifi_ip ──────────────────────────────────────────────────────────

@test "detect_wifi_ip extracts IPv4 address from Wi-Fi interface" {
  cat > "${TEST_BINDIR}/ip_addr_wlp2s0" << 'EOF'
3: wlp2s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    inet 10.0.1.5/24 brd 10.0.1.255 scope global wlp2s0
       valid_lft forever preferred_lft forever
EOF
  source "${SCRIPT_DIR}/lib/detect.sh"
  result="$(detect_wifi_ip "wlp2s0")"
  [[ "${result}" == "10.0.1.5/24" ]]
}

# ── suggest_vmbr_ip ─────────────────────────────────────────────────────────

@test "suggest_vmbr_ip fallback chain: vmbr0 IP > wifi IP > gw subnet > default" {
  source "${SCRIPT_DIR}/lib/detect.sh"

  # ── 1. Existing vmbr0 IP is returned first ──
  cat > "${TEST_BINDIR}/ip_addr_vmbr0" << 'EOF'
2: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    inet 10.0.0.5/24 brd 10.0.0.255 scope global vmbr0
       valid_lft forever preferred_lft forever
EOF
  cat > "${TEST_BINDIR}/ip_addr_wlp2s0" << 'EOF'
3: wlp2s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    inet 10.0.1.5/24 brd 10.0.1.255 scope global wlp2s0
       valid_lft forever preferred_lft forever
EOF
  result="$(suggest_vmbr_ip "10.0.0.1" "wlp2s0")"
  [[ "${result}" == "10.0.0.5/24" ]]

  # ── 2. No vmbr0 IP → Wi-Fi IP is returned ──
  rm -f "${TEST_BINDIR}/ip_addr_vmbr0"
  # (ip_addr_wlp2s0 still present from above)
  result="$(suggest_vmbr_ip "10.0.0.1" "wlp2s0")"
  [[ "${result}" == "10.0.1.5/24" ]]

  # ── 3. No vmbr0 or Wi-Fi IP → gateway subnet .130/24 ──
  rm -f "${TEST_BINDIR}/ip_addr_wlp2s0"
  result="$(suggest_vmbr_ip "10.0.0.1" "wlp2s0")"
  [[ "${result}" == "10.0.0.130/24" ]]

  # ── 4. No vmbr0, Wi-Fi, or valid gateway → default ──
  result="$(suggest_vmbr_ip "" "wlp2s0")"
  [[ "${result}" == "192.168.1.100/24" ]]
}
