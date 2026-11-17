---
name: proxmox-node
description: Configure a Proxmox hypervisor in AUTOLAB, onboard a new node, or build a VM template. Use for node accounts, storage, the backup job, Pocket ID on the node, a new machine to run VMs on, or a new OS template.
---

# A Proxmox node

A node is configured by `playbooks/proxmox.yml` through workflow `07`, not
by the VM baseline: its sshd carries cluster traffic and it has its own
firewall. Nodes today: `xps-pve` (`lab`), `pve` (the tenant), `zima-pve`
(`edge`). They are peers at the repository level, not a cluster.

## Configuring a node

1. Edit `playbooks/proxmox.yml` or the `proxmox-*` roles. `pull-request`.
2. `run-workflow`: `07`, `playbook=proxmox`, `limit=<node>`,
   `bootstrap=false`, check then apply. `tags` narrows it (`updates` for
   packages).
3. Done when the apply's recap has no failures and the thing changed is
   visible on the node (`pvesm status`, the backup job under Datacenter →
   Backup, the realm on the login page).

Updates and reboots: `updates`. The backup job and its storage:
`backup-restore`. The node's OpenID realm: `docs/gitops/ingress.md`,
"Proxmox and PBS on the same login".

## Onboarding a new node

By hand first, because nothing can reach it yet: install Proxmox, get it on
the network, join it to the tailnet (`docs/proxmox/`, the bootstrap phase).
Then:

1. An API token for it, and its secret `PROXMOX_API_TOKEN_<NODE>`
   (`docs/gitops/03-proxmox-api-token.md`): `secret`.
2. Add the node to the `node` choices in workflows `01` and `02`, and to
   `autolab_obs_pve_nodes`, the nodes the observability role monitors.
3. `01` for the node: its private VM network.
4. `07`, `playbook=proxmox`, `limit=<node>`, `bootstrap=true` for this first
   run only: accounts, repositories, the backup storage.
5. A template on it: below.
6. A Stack for its machines when it is not joining an existing one:
   copy `infra/stacks/_template`, add the Stack to the `environment` choices
   in `03`, `04`, `05` and `99`, and a GitHub Environment of the same name.
7. `observe` and `surfaces`: the node's row on home and its tile on dash
   build from the node list; `docs/gitops/naming.md` gets its name.

## A template

Templates are immutable releases: a new one is built beside the old, and
machines are switched to it deliberately
(`docs/gitops/template-lifecycle.md`).

1. A new release is a new entry in `infra/packer/template-catalog.yaml` with
   an unused VM ID. An existing release is never overwritten.
2. `02`, `template=<name>`, `node=<node>`. `force_rebuild=true` only to
   replace a failed build's leftover.
3. Prove it by cloning a disposable VM from it (`sputnik` is for this) and
   running `harden` on it.
4. Point machines at it by changing their `template_vm_id`. That replaces
   the VM, so it is a `new-vm` rebuild, one machine at a time.

## Guardrails

- xps-pve is full: say how much memory is left before adding to it.
- A node reboot stops every guest on it: `updates`.
