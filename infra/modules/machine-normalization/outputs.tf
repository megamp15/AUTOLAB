output "normalized_machines" {
  description = "Machine declarations with Stack defaults merged in."
  value       = local.normalized_machines

  # One stack talks to one node's API. The nodes are not clustered, so a
  # machine placed on another node is one this stack's provider cannot reach:
  # it fails halfway through an apply rather than here.
  precondition {
    condition = alltrue([
      for _, machine in local.normalized_machines : machine.node_name == var.default_node_name
    ])
    error_message = "Every Machine in a Stack must live on the Stack's node (node.auto.tfvars). The nodes are not clustered; a Machine for another node belongs in that node's Stack."
  }
}

output "builder_target_machines" {
  description = "Normalized Machines that use the Linux builder-target provisioning path."
  value       = local.builder_target_machines
}

output "builder_target_vm_machines" {
  description = "Normalized VM Machines that need cloud-init user data for the builder-target path."
  value       = local.builder_target_vm_machines

  # A leased address is unknowable at plan time, and the plan is where the
  # Builder inventory comes from. Fail here, before anything is created, rather
  # than with an inventory that names a VM nothing can dial.
  precondition {
    condition = !var.management_plane || alltrue([
      for _, machine in local.builder_target_vm_machines :
      machine.management_address != null && machine.ipv4_gateway != null
    ])
    error_message = "On the management plane every builder_target Machine needs a static ipv4_address (CIDR) and an ipv4_gateway; \"dhcp\" cannot be dialled through the hypervisor."
  }

  precondition {
    condition = alltrue(flatten([
      for _, machine in local.builder_target_vm_machines : [
        for entry in machine.builder.storage :
        entry.server != null && contains(["nfs", "smb"], entry.protocol) && (entry.protocol != "smb" || entry.credential != null)
      ]
    ]))
    error_message = "Each storage entry needs a server (or the Stack's nas_server / NAS_SERVER), protocol nfs or smb, and — for smb — a credential name."
  }
}

output "cluster_os_machines" {
  description = "Normalized Cluster OS Machines. Reserved for future Talos-style provisioning."
  value       = local.cluster_os_machines
}
