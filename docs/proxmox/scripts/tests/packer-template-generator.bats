#!/usr/bin/env bats
# Tests for scripts/generate-packer-template-adapters.sh generator logic.

bats_require_minimum_version 1.5.0

load test_helper

setup() {
  export AUTOLAB_GENERATOR_LIB_ONLY=1
  source "${SCRIPT_DIR}/../../../scripts/generate-packer-template-adapters.sh"
}

@test "packer template schema carries CI variable names" {
  [ "$(schema_field 0 '.ci_env')" = "PACKER_SSH_PASSWORD" ]
  [ "$(schema_field 1 '.ci_env')" = "PROXMOX_STORAGE_POOL" ]
  [ "$(schema_field 2 '.ci_env')" = "PROXMOX_NETWORK_BRIDGE" ]
  [ "$(schema_field 3 '.ci_env')" = "PACKER_ISO_URL" ]
  [ "$(schema_field 4 '.ci_env')" = "PACKER_ISO_CHECKSUM" ]
  [ "$(schema_field 3 '.required_in_ci')" = "true" ]
  [ "$(schema_field 4 '.required_in_ci')" = "true" ]
}

@test "packer template schema carries Packer variable names" {
  [ "$(schema_field 0 '.packer_var')" = "ssh_password" ]
  [ "$(schema_field 5 '.packer_var')" = "cloud_init_storage_pool" ]
  [ "$(schema_field 6 '.packer_var')" = "ssh_public_keys" ]
}

@test "generated Packer template adapter matches schema" {
  run env -u AUTOLAB_GENERATOR_LIB_ONLY bash "${SCRIPT_DIR}/../../../scripts/generate-packer-template-adapters.sh" --check
  [ "$status" -eq 0 ]
  [[ "$output" == *"matches schema"* ]]
  grep -A2 '^  iso_url:' "${SCRIPT_DIR}/../../../.github/actions/configure-packer-template/action.yml" | grep -q 'required: true'
  grep -A2 '^  iso_checksum:' "${SCRIPT_DIR}/../../../.github/actions/configure-packer-template/action.yml" | grep -q 'required: true'
}
