#!/usr/bin/env bats
# Tests for scripts/generate-connection-adapters.sh generator logic.

bats_require_minimum_version 1.5.0

load test_helper

setup() {
  export AUTOLAB_GENERATOR_LIB_ONLY=1
  source "${SCRIPT_DIR}/../../../scripts/generate-connection-adapters.sh"
}

@test "schema_type_to_hcl maps supported scalar types" {
  [ "$(schema_type_to_hcl string)" = "string" ]
  [ "$(schema_type_to_hcl bool)" = "bool" ]
  [ "$(schema_type_to_hcl number)" = "number" ]
  run schema_type_to_hcl unknown
  [ "$status" -ne 0 ]
  [[ "$output" == *"unsupported schema type"* ]]
}

@test "connection schema carries module variable names" {
  [ "$(schema_field 0 '.ci_env')" = "PROXMOX_HOST" ]
  [ "$(schema_field 1 '.ci_env')" = "PROXMOX_PORT" ]
  [ "$(schema_field 2 '.module_var')" = "endpoint" ]
  [ "$(schema_field 3 '.module_var')" = "api_token" ]
  [ "$(schema_field 4 '.module_var')" = "node_name" ]
  [ "$(schema_field 5 '.module_var')" = "insecure_tls" ]
}

@test "connection schema carries validation messages" {
  run schema_field 3 '.error_message'
  [ "$status" -eq 0 ]
  [[ "$output" == *"USER@REALM!TOKENID=TOKEN_SECRET"* ]]
}

@test "generated module adapter uses schema module_var names" {
  run bash "${SCRIPT_DIR}/../../../scripts/generate-connection-adapters.sh" --opentofu --check
  [ "$status" -eq 0 ]

  [[ "$(schema_field 2 '.module_var')" = "endpoint" ]]
  [[ -f "${SCRIPT_DIR}/../../../infra/modules/proxmox-connection/variables.tf" ]]
}

@test "connection adapter derives default and IPv6 endpoints" {
  [ "$(format_proxmox_endpoint pve.example.test 8006)" = "https://pve.example.test:8006" ]
  [ "$(format_proxmox_endpoint pve.example.test 9443)" = "https://pve.example.test:9443" ]
  [ "$(format_proxmox_endpoint 2001:db8::10 8006)" = "https://[2001:db8::10]:8006" ]
  [ "$(format_proxmox_endpoint '[2001:db8::10]' 8006)" = "https://[2001:db8::10]:8006" ]
  action="${SCRIPT_DIR}/../../../.github/actions/configure-proxmox-connection/action.yml"
  grep -q 'format_proxmox_endpoint' "$action"
  grep -q 'AUTOLAB_INPUT_PROXMOX_PORT' "$action"
  grep -q "default: '8006'" "$action"
  grep -q 'host="\[\$host\]"' "$action"
  ! grep -q 'PROXMOX_ENDPOINT' "$action"
}
