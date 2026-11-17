---
name: updates
description: Apply package updates and reboots in AUTOLAB, on VMs and on Proxmox nodes. Use for the pending-updates reminder, a security advisory, a kernel waiting for a reboot, or a Tailscale or image version bump.
---

# Updates and reboots

What runs by itself and when: `docs/gitops/operations.md`, "Scheduled work".

## What is already automatic

- Security updates on every VM, through the distribution's unattended
  upgrades, from the baseline.
- A report of pending packages four times a day, and a reminder every four
  days while any are pending.
- Diun, daily: a notification when a pinned image has a newer tag. It
  changes nothing.

Everything below is a deliberate run.

## VMs: all pending packages

1. `run-workflow`: `05`, `playbook=updates`, the Stack as `environment`,
   check, then apply. It goes one host at a time and stops at the first that
   fails. It reboots nothing and reports which hosts need one.
2. Reboot those: `05`, `playbook=reboot`, `confirm=apply`. One host at a
   time, each waited for; hosts that do not need it are left alone.
   `force_reboot=true` reboots regardless.
3. Order matters for the machines others depend on. Reboot horizon (every
   name), jwst (monitoring, the services) and ark (backups) one at a time
   with `limit=<name>`, outside 02:00-04:30 when backups and their checks run.

Done when the run's report lists no host needing a reboot, and home is green.

## Nodes

A node reboot stops every guest on it.

1. `07`, `playbook=proxmox`, `tags=updates`, `bootstrap=false`, `limit=<node>`,
   check then apply.
2. If a kernel is waiting: `07`, `playbook=reboot`, `limit=<node>` (exactly
   one), `bootstrap=false`, `confirm=reboot`. It refuses to start while a
   running guest is not marked start-on-boot, and names it. Afterwards it
   waits for every guest that was running.
3. Tell the user what goes down before step 2: xps-pve takes jwst, horizon
   and ark with it, so every name and all monitoring.

## Versions pinned in git

| what | where the pin is | run |
|---|---|---|
| a container image | `autolab_services_images`, `autolab_ingress_images`, the observability role's defaults | `05` for that role |
| Tailscale on VMs | follows stable from the apt repository | `05` `tailscale-update` |
| the VM template | a new release in `infra/packer/template-catalog.yaml` | `proxmox-node`, "A template" |

A bump is a pull request: read the release notes for a migration or a
breaking change first, and say what you found in the body.

## Guardrails

- `08` for the guest (or `all`) before a risky update.
- A node reboot, or `limit=all` on updates, is named to the user before it
  starts.
