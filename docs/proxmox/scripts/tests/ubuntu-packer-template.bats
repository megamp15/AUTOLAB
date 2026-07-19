#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load test_helper

TEMPLATE_DIR="${SCRIPT_DIR}/../../../infra/packer/templates/ubuntu-26.04"

@test "Ubuntu template uses a cidata seed CD instead of runner HTTP" {
  run grep -E 'additional_iso_files|cd_content|cd_label[[:space:]]*= "cidata"|iso_storage_pool[[:space:]]*= "local"|"user-data"|"meta-data"' \
    "${TEMPLATE_DIR}/ubuntu-26.04.pkr.hcl"
  [ "$status" -eq 0 ]
  ! grep -q 'http_content\|HTTPIP\|HTTPPort\|nocloud-net;s=http' "${TEMPLATE_DIR}/ubuntu-26.04.pkr.hcl"
  grep -q 'autoinstall' "${TEMPLATE_DIR}/ubuntu-26.04.pkr.hcl"
  grep -q 'cd_label[[:space:]]*= "cidata"' "${TEMPLATE_DIR}/ubuntu-26.04.pkr.hcl"
}

@test "Ubuntu seed handles SSH keys and grants temporary sudo" {
  grep -q 'authorized-keys: ${jsonencode(ssh_keys)}' "${TEMPLATE_DIR}/user-data"
  grep -q 'NOPASSWD:ALL' "${TEMPLATE_DIR}/user-data"
  grep -q 'rm -f /etc/sudoers.d/90-autolab-packer' "${TEMPLATE_DIR}/ubuntu-26.04.pkr.hcl"
}

@test "setup action derives and exports the temporary password hash" {
  action="${SCRIPT_DIR}/../../../.github/actions/setup-packer-pipeline/action.yml"
  grep -q 'openssl passwd -6 -stdin' "$action"
  grep -q 'add-mask' "$action"
  grep -q 'PKR_VAR_packer_password_hash' "$action"
}

@test "hosted setup requires and wires the SSH bastion" {
  action="${SCRIPT_DIR}/../../../.github/actions/setup-packer-pipeline/action.yml"
  workflow="${SCRIPT_DIR}/../../../.github/workflows/packer-build.yml"
  grep -q 'pve_ssh_private_key:' "$action"
  grep -q 'PVE_SSH_PRIVATE_KEY is required' "$action"
  grep -q 'PKR_VAR_ssh_bastion_host' "$action"
  grep -q 'PKR_VAR_ssh_bastion_private_key_file' "$action"
  grep -q 'pve_ssh_private_key:.*secrets.PVE_SSH_PRIVATE_KEY' "$workflow"
  grep -q 'pve_ssh_username: root' "$workflow"
}

@test "Packer build does not force-overwrite catalog VM IDs" {
  workflow="${SCRIPT_DIR}/../../../.github/workflows/packer-build.yml"
  ! grep -q 'force_rebuild\|-force' "$workflow"
  grep -q 'xorriso' "${SCRIPT_DIR}/../../../.github/actions/setup-packer-pipeline/action.yml"
}

@test "Ubuntu zeroes free space before final hardening" {
  hcl="${TEMPLATE_DIR}/ubuntu-26.04.pkr.hcl"
  zero_line="$(grep -n 'dd if=/dev/zero' "$hcl" | cut -d: -f1)"
  hardening_line="$(grep -n 'rm -f /etc/sudoers.d/90-autolab-packer' "$hcl" | cut -d: -f1)"
  [ "$zero_line" -lt "$hardening_line" ]
}

@test "Ubuntu password hash is required and has no source default" {
  vars="${TEMPLATE_DIR}/template-vars.pkr.hcl"
  grep -A4 '^variable "packer_password_hash"' "$vars" | grep -q 'sensitive   = true'
  ! grep -A6 '^variable "packer_password_hash"' "$vars" | grep -q 'default'
  ! grep -A8 '^variable "vm_id"' "$vars" | grep -q 'default'
  ! grep -A8 '^variable "vm_template_name"' "$vars" | grep -q 'default'
}
