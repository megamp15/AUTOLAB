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
  id          = "01ef5c8e-7a2d-4b9f-b8e3-1c2d3e4f5a6b"
  name        = "Lab"
  description = "First homelab environment on the XPS 9560 Proxmox node"
  tags        = ["lab", "proxmox"]
}
