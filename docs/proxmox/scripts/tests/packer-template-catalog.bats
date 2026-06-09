#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load test_helper

@test "resolve-packer-template.sh resolves debian-12" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" debian-12
  [ "$status" -eq 0 ]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE=debian-12"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_FILE=infra/packer/debian-12.pkr.hcl"* ]]
}

@test "resolve-packer-template.sh rejects unknown templates" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" unknown-template
  [ "$status" -ne 0 ]
  [[ "$output" == *"Unknown Packer template"* ]]
}
