---
name: new-vm
description: Stand up a new VM in AUTOLAB from the machines map to a hardened, monitored, backed-up host. Use to add a machine, resize or rename one, or remove one.
---

# A new VM

A machine is one entry in `infra/stacks/<stack>/machines.auto.tfvars`.
Everything about it follows from that entry: OpenTofu creates it, cloud-init
enrols it on the tailnet, the Builder configures it from its `builder` block.

## Before writing it

- **Name**: for what it does, from the pools in `docs/gitops/naming.md`. A
  rename later rebuilds the VM, so settle it now.
- **Stack and node**: `lab` on xps-pve (full: check free memory first),
  `edge` on zima-pve, a tenant's own Stack on `pve`. Copy the `node_name`,
  `template_vm_id` and datastores from a neighbour in the same Stack.
- **VMID**: the next free one in the Stack's range. In `lab`, 102 and 103
  stay free for restore tests.
- **Address**: `dhcp` unless something must dial it at a known address; then
  a static one on the Stack's bridge, by the convention in the map's comments.
- **Size**: memory is the scarce thing. Say what is left on the node.

## Steps

1. Write the entry, with a comment saying what the machine is for and why it
   is this size. Set only the `builder` options it needs:

   | option | gives it | then run (`05`) |
   |---|---|---|
   | (none) | the baseline: accounts, sshd, firewall, fail2ban, security updates, the agent | `harden` |
   | `firewall_rules` | ports open beyond the baseline | `harden` |
   | `docker_enabled = true` | Docker | `docker`, then `docker-management` |
   | `storage = [...]` | NAS mounts | `storage` (and a NAS export rule by hand: `nas`) |
   | `services = [...]` | container services | `services`: see `service` |
   | `observability = { ship_to = "jwst" }` | where its agent sends, outside `lab` | `observability` |

2. `pull-request`. `tofu fmt -check -recursive infra` passes.
3. After the merge, `run-workflow`: `03` plan for the Stack. Done when the
   plan adds this machine and changes nothing else. A plan that replaces
   another VM is a stop.
4. `04` apply. The VM boots and joins the tailnet by itself within a few
   minutes.
5. `05` `harden` with `bootstrap=true`, `limit=<name>`, check then apply.
   This is the step that is forgotten: until it runs, the machine has no
   `gitops` account and every later `05` run fails for every host.
6. The playbooks from the table, in the order listed, each check then apply,
   each with `limit=<name>`.
7. `observe`: the host reports.
8. Backups: the node's nightly job covers every guest it does not exclude,
   so a new VM is in it from the next 02:00. `backup-restore` to back it up
   now and to prove a restore once it holds something.
9. `surfaces`: `docs/gitops/naming.md` ("In use"), and its own page when it
   hosts more than one thing. Home's machine rows build themselves.

## Proof

- `ssh megamp15@<name>` works over the tailnet; `ssh root@<name>` is refused.
- Its row on home's Architecture tab is green and Grafana has its metrics.
- `sudo ufw status` on it shows only what the entry declared.

## Changing or removing one

- **Resize**: edit the entry; `03`, `04`. More memory or cores restarts the
  VM. A disk grows and never shrinks.
- **Rename**: it is a rebuild, on purpose. Let it destroy and recreate; a
  `moved` block skips the Tailscale cleanup and leaves an orphaned device
  (`docs/gitops/naming.md`). The new machine has a new tailnet address, so
  NAS export rules keyed to the old one are redone by hand.
- **Remove**: delete the entry; `03` (the plan destroys exactly that
  machine), `04`. Its tailnet device is deleted by the destroy hook. Then
  `surfaces`. `99` destroys a whole Stack and is not the way to remove one VM.

## Guardrails

- Back up first when the machine being changed holds data: `08`.
- A machine that will hold a database keeps it on its own disk, with dumps
  to the NAS, never on NFS (`docs/gitops/nebula.md`).
