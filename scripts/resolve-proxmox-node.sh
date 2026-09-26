#!/bin/bash
# resolve-proxmox-node.sh — Name a Proxmox node and the key its secrets use.
#
# The nodes are independent, not clustered, so everything that talks to one
# needs to know which. A Stack says so in its node.auto.tfvars; a workflow that
# targets a node directly (network bootstrap, Packer) takes the name as input.
# Either way the output is the same two lines, ready for $GITHUB_OUTPUT:
#
#   name=xps-pve
#   key=XPS_PVE
#
# The key is how per-node repository secrets are named:
# PROXMOX_API_TOKEN_<key>. Host names are not stored per node at all; they are
# <name>.<TAILNET_DOMAIN>, which the caller composes.
#
# Usage:
#   resolve-proxmox-node.sh --stack infra/stacks/lab
#   resolve-proxmox-node.sh --node pve
set -euo pipefail

usage() {
  echo "usage: $0 --stack <stack-dir> | --node <node-name>" >&2
  exit 2
}

[[ $# -eq 2 ]] || usage

case "$1" in
  --stack)
    file="$2/node.auto.tfvars"
    if [[ ! -f "$file" ]]; then
      echo "ERROR: $file is missing; a Stack names its Proxmox node there." >&2
      exit 1
    fi
    name="$(sed -n 's/^[[:space:]]*proxmox_node_name[[:space:]]*=[[:space:]]*"\([^"]*\)"[[:space:]]*$/\1/p' "$file")"
    if [[ -z "$name" ]]; then
      echo "ERROR: $file does not set proxmox_node_name = \"<node>\"." >&2
      exit 1
    fi
    ;;
  --node)
    name="$2"
    ;;
  *)
    usage
    ;;
esac

# The same rule the OpenTofu variable enforces, so a bad name fails here with
# a message rather than as a secret lookup that quietly returns nothing.
if [[ ! "$name" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]*$ ]]; then
  echo "ERROR: '$name' is not a valid Proxmox node name." >&2
  exit 1
fi

key="$(printf '%s' "$name" | tr '[:lower:]-' '[:upper:]_')"

printf 'name=%s\n' "$name"
printf 'key=%s\n' "$key"
