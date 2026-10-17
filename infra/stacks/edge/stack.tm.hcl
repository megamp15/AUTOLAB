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
  id          = "efebc53b-fee6-42be-a688-4b4ea7cc7ff2"
  name        = "Edge"
  description = "The home network's edge on zima-pve: DNS with ad blocking (magnetosphere) and the router (lagrange)"
  tags        = ["edge", "network", "proxmox"]
}
