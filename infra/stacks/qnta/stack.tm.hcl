import {
  source = "/infra/_base/backend.tm.hcl"
}

import {
  source = "/infra/_base/connection-variables.tm.hcl"
}

import {
  source = "/infra/_base/providers.tm.hcl"
}

stack {
  id          = "6f2d9c1e-4b7a-4e3c-9a58-2d1f0c7b8e45"
  name        = "QNTA"
  description = "Tenant stack: business VMs on the shared hypervisor, enrolled on the tenant's own tailnet"
  tags        = ["qnta", "tenant", "proxmox"]
}
