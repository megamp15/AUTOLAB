module "proxmox" {
  source = "../../modules/proxmox-connection"

  endpoint     = var.proxmox_endpoint
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

module "cloud_init" {
  for_each = module.machine_inputs.builder_target_vm_machines

  source = "../../modules/cloud-init"

  hostname           = each.value.name
  admin_username     = each.value.admin_username
  ssh_public_keys    = each.value.ssh_public_keys
  tailscale_auth_key = var.tailscale_auth_key
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
  template_vm_id          = each.value.template_vm_id
  template_node_name      = each.value.template_node_name
  cloud_init_datastore_id = each.value.cloud_init_datastore_id
  admin_username          = each.value.admin_username
  cloud_init_user_data    = try(module.cloud_init[each.key].user_data, "")

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
