locals {
  normalized_machines = {
    for key, machine in var.machines : key => merge(machine, {
      node_name          = coalesce(machine.node_name, module.proxmox.node_name)
      admin_username     = coalesce(machine.admin_username, var.identity_defaults.admin_username)
      network_bridge     = var.network_defaults.network_bridge
      vlan_id            = var.network_defaults.vlan_id
      ssh_public_keys    = var.identity_defaults.ssh_public_keys
      tags               = concat(var.common_tags, [machine.type])
      tailscale_auth_key = var.tailscale_auth_key
    })
  }

  vm_machines = {
    for key, machine in local.normalized_machines : key => machine
    if machine.type == "vm"
  }
}

module "proxmox" {
  source = "../../modules/proxmox-connection"

  endpoint     = var.proxmox_endpoint
  api_token    = var.proxmox_api_token
  insecure_tls = var.proxmox_insecure_tls
  node_name    = var.proxmox_node_name
}

module "cloud_init" {
  for_each = local.vm_machines

  source = "../../modules/cloud-init"

  hostname           = each.value.name
  admin_username     = each.value.admin_username
  ssh_public_keys    = each.value.ssh_public_keys
  tailscale_auth_key = each.value.tailscale_auth_key
}

module "machine" {
  source   = "../../modules/proxmox-compute"
  for_each = local.normalized_machines

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
