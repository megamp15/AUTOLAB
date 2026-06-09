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
  id          = "REPLACE-WITH-UUID"
  name        = "REPLACE-WITH-NAME"
  description = "REPLACE-WITH-DESCRIPTION"
  tags        = ["autolab"]
}
