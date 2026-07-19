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
  [ "$(schema_field 3 '.ci_env')" = "PROXMOX_CLOUD_INIT_STORAGE_POOL" ]
  [ "$(schema_field 4 '.ci_env')" = "SSH_PUBLIC_KEYS" ]
}

@test "packer template schema carries Packer variable names" {
  [ "$(schema_field 0 '.packer_var')" = "ssh_password" ]
  [ "$(schema_field 3 '.packer_var')" = "cloud_init_storage_pool" ]
  [ "$(schema_field 4 '.packer_var')" = "ssh_public_keys" ]
}

@test "generated Packer template adapter matches schema" {
  run env -u AUTOLAB_GENERATOR_LIB_ONLY bash "${SCRIPT_DIR}/../../../scripts/generate-packer-template-adapters.sh" --check
  [ "$status" -eq 0 ]
  [[ "$output" == *"matches schema"* ]]
  ! grep -q 'iso_url\|iso_checksum\|PACKER_ISO_URL\|PACKER_ISO_CHECKSUM' "${SCRIPT_DIR}/../../../.github/actions/configure-packer-template/action.yml"
}
