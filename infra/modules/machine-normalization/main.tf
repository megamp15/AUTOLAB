locals {
  normalized_machines = {
    for key, machine in var.machines : key => merge(machine, {
      node_name       = coalesce(machine.node_name, var.default_node_name)
      admin_username  = coalesce(machine.admin_username, var.identity_defaults.admin_username)
      network_bridge  = var.network_defaults.network_bridge
      vlan_id         = var.network_defaults.vlan_id
      ssh_public_keys = var.identity_defaults.ssh_public_keys
      tags            = concat(var.common_tags, [machine.type])
    })
  }

  vm_machines = {
    for key, machine in local.normalized_machines : key => machine
    if machine.type == "vm"
  }
}
