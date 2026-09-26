# The Proxmox node this Stack's machines live on. The nodes are independent,
# not clustered, so a Stack talks to exactly one node's API.
#
# Workflows read this file to pick the node's credentials: the host is
# <node>.<TAILNET_DOMAIN>, and the token is the repository secret
# PROXMOX_API_TOKEN_<NODE>, upper-cased with dashes as underscores.
proxmox_node_name = "xps-pve"
