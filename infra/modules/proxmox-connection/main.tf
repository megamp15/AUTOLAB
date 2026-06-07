# proxmox-connection — validates and normalises Proxmox connection config.
#
# This module is the single source of truth for "how we connect to Proxmox".
# It validates connection parameters at plan time and provides derived values
# that compute modules consume through one module call.
#
# The OpenTofu provider block cannot reference module outputs, so it still
# reads from var.proxmox_* directly. This module exists to:
#   1. Validate connection parameters at plan time
#   2. Provide a single source of truth for node_name and derived values
#   3. Let compute modules consume connection config through one module call
#
# Schema source: infra/connection-schema.yaml

locals {
  # Normalised endpoint without trailing slash
  endpoint_normalised = trimsuffix(var.endpoint, "/")

  # Derived: the Proxmox web UI URL
  web_ui_url = "${local.endpoint_normalised}/"
}