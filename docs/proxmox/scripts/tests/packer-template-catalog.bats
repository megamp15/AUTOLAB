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
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_RELEASE=13.6.0"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_VM_ID=9000"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME=autolab-debian-13-template"* ]]
  [[ "$output" == *"PKR_VAR_vm_id=9000"* ]]
  [[ "$output" == *"PKR_VAR_vm_template_name=autolab-debian-13-template"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_ISO_URL=https://cdimage.debian.org/debian-cd/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM=sha256:65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7"* ]]
  [[ "$output" == *"PKR_VAR_iso_url=https://cdimage.debian.org/debian-cd/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso"* ]]
  [[ "$output" == *"PKR_VAR_iso_checksum=sha256:65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7"* ]]
}

@test "resolve-packer-template.sh rejects invalid catalog checksum" {
  catalog="${SCRIPT_DIR}/../../../infra/packer/template-catalog.yaml"
  backup="$(mktemp)"
  cp "$catalog" "$backup"
  yq -i '.templates[0].iso_checksum = "sha256:invalid"' "$catalog"
  status=0
  output="$(bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" debian-13 2>&1)" || status=$?
  cp "$backup" "$catalog"
  rm -f "$backup"
  [ "$status" -ne 0 ]
  [[ "$output" == *"invalid iso_checksum"* ]]
}

@test "resolve-packer-template.sh rejects invalid catalog URL" {
  catalog="${SCRIPT_DIR}/../../../infra/packer/template-catalog.yaml"
  backup="$(mktemp)"
  cp "$catalog" "$backup"
  yq -i '.templates[0].iso_url = "not-a-url"' "$catalog"
  status=0
  output="$(bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" debian-13 2>&1)" || status=$?
  cp "$backup" "$catalog"
  rm -f "$backup"
  [ "$status" -ne 0 ]
  [[ "$output" == *"invalid iso_url"* ]]
}

@test "resolve-packer-template.sh resolves runnable ubuntu-24.04 from catalog" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" ubuntu-24.04
  [ "$status" -eq 0 ]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE=ubuntu-24.04"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_FILE=infra/packer/templates/ubuntu-24.04/ubuntu-24.04.pkr.hcl"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_DIR=infra/packer/templates/ubuntu-24.04"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_STATUS=implemented"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_RELEASE=24.04.3"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_VM_ID=9002"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_PROXMOX_NAME=autolab-ubuntu-24.04-template"* ]]
  [[ "$output" == *"PKR_VAR_vm_id=9002"* ]]
  [[ "$output" == *"PKR_VAR_vm_template_name=autolab-ubuntu-24.04-template"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_ISO_URL=https://releases.ubuntu.com/24.04.3/ubuntu-24.04.3-live-server-amd64.iso"* ]]
  [[ "$output" == *"AUTOLAB_PACKER_TEMPLATE_ISO_CHECKSUM=sha256:c3514bf0056180d09376462a7a1b4f213c1d6e8ea67fae5c25099c6fd3d8274b"* ]]
  [[ "$output" == *"PKR_VAR_iso_url=https://releases.ubuntu.com/24.04.3/ubuntu-24.04.3-live-server-amd64.iso"* ]]
  [[ "$output" == *"PKR_VAR_iso_checksum=sha256:c3514bf0056180d09376462a7a1b4f213c1d6e8ea67fae5c25099c6fd3d8274b"* ]]
}

@test "resolve-packer-template.sh rejects blocked ubuntu-26.04" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" ubuntu-26.04
  [ "$status" -ne 0 ]
  [[ "$output" == *"not implemented (status=blocked)"* ]]
}

@test "resolve-packer-template.sh rejects unknown templates" {
  run bash "${SCRIPT_DIR}/../../../scripts/resolve-packer-template.sh" unknown-template
  [ "$status" -ne 0 ]
  [[ "$output" == *"Unknown Packer template"* ]]
}
