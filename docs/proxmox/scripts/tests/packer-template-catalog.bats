#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load test_helper

@test "resolve-packer-template.sh resolves debian-13 from catalog" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" debian-13
  [ "$status" -eq 0 ]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE=debian-13"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_FILE=infra/packer/templates/debian-13/debian-13.pkr.hcl"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_DIR=infra/packer/templates/debian-13"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_STATUS=implemented"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_VM_ID=9000"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME=autolab-debian-13-template"* ]]
}

@test "resolve-packer-template.sh rejects experiment-only templates" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" ubuntu-24.04
  [ "$status" -ne 0 ]
  [[ "$output" == *"disposable experiment target"* ]]
}

@test "resolve-packer-template.sh rejects unknown templates" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" unknown-template
  [ "$status" -ne 0 ]
  [[ "$output" == *"Unknown Packer template"* ]]
}
