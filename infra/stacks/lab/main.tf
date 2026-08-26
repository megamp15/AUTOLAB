module "proxmox" {
  source = "../../modules/proxmox-connection"

  endpoint     = local.proxmox_endpoint
  api_token    = var.proxmox_api_token
  insecure_tls = var.proxmox_insecure_tls
  node_name    = var.proxmox_node_name
}

module "machine_inputs" {
  source = "../../modules/machine-normalization"

  machines          = var.machines
  default_node_name = module.proxmox.node_name
  network_defaults  = var.network_defaults
  identity_defaults = var.identity_defaults
  common_tags       = var.common_tags
}

resource "tailscale_tailnet_key" "builder_target_vm" {
  for_each = module.machine_inputs.builder_target_vm_machines

  reusable      = true
  ephemeral     = false
  preauthorized = true
  expiry        = 3600
  # Join key is for initial provisioning only; a running VM keeps its identity
  # in /var/lib/tailscale/tailscaled.state. Replacing an expired key here would
  # churn the cloud-init snippet and force-replace the VM on every apply.
  recreate_if_invalid = "never"
  tags                = ["tag:autolab-vm"]
}

module "cloud_init" {
  for_each = module.machine_inputs.builder_target_vm_machines

  source = "../../modules/cloud-init"

  hostname           = each.value.name
  admin_username     = each.value.admin_username
  ssh_public_keys    = each.value.ssh_public_keys
  tailscale_auth_key = tailscale_tailnet_key.builder_target_vm[each.key].key
}

module "machine" {
  source   = "../../modules/proxmox-compute"
  for_each = module.machine_inputs.builder_target_machines

  # Type selector
  type = each.value.type

  # Identity
  name      = each.value.name
  vm_id     = each.value.vm_id
  node_name = each.value.node_name

  # VM-specific
  template_vm_id                  = each.value.template_vm_id
  template_node_name              = each.value.template_node_name
  cloud_init_datastore_id         = each.value.cloud_init_datastore_id
  cloud_init_enabled              = each.value.type == "vm"
  cloud_init_snippet_datastore_id = var.cloud_init_snippet_datastore_id
  admin_username                  = each.value.admin_username
  cloud_init_user_data            = try(module.cloud_init[each.key].user_data, "")

  # LXC-specific
  template_file_id = each.value.template_file_id
  os_type          = each.value.os_type

  # Shared compute
  datastore_id    = each.value.datastore_id
  network_bridge  = each.value.network_bridge
  vlan_id         = each.value.vlan_id
  cpu_cores       = each.value.cpu_cores
  memory_mb       = each.value.memory_mb
  disk_size_gb    = each.value.disk_size_gb
  ssh_public_keys = each.value.ssh_public_keys
  ipv4_address    = each.value.ipv4_address
  ipv4_gateway    = each.value.ipv4_gateway
  tags            = each.value.tags
  started         = each.value.started
}

# Tailscale device cleanup — revoke the VM's device record when the VM dies.
#
# VMs join Tailscale asynchronously via cloud-init, so their device IDs are
# unknowable at plan time. Instead of tracking IDs in state, destroy-time
# resolution is by deterministic hostname + tag:autolab-vm (see
# scripts/tailscale-device-delete.sh and docs/gitops/tailscale-device-lifecycle.md).
#
# Why this shape:
#   - depends_on reverses on destroy, so the device is revoked BEFORE the
#     disk is destroyed — while the VM still exists to be matched by name.
#   - triggers_replace on vm_id also cleans up stale devices when the VM is
#     rebuilt from a new template (old device revoked before the new one joins).
#   - local-exec runs wherever tofu runs; TAILSCALE_OAUTH_CLIENT_ID/SECRET come
#     from the destroy workflow's exported env (or your local shell).
#
# Destroy-time provisioners may only reference `self`, so the hostname is
# stashed in `input` (persisted state) and read back as self.input.
resource "terraform_data" "tailscale_device_cleanup" {
  for_each = module.machine_inputs.builder_target_vm_machines

  input            = each.value.name
  triggers_replace = [module.machine[each.key].vm_id]

  provisioner "local-exec" {
    when    = destroy
    command = "${path.module}/../../scripts/tailscale-device-delete.sh ${self.input}"
  }

  depends_on = [module.machine]
}
