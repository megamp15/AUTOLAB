---
name: run-workflow
description: Deploy an AUTOLAB change - which GitHub workflow to dispatch, in what order, with which inputs, and how to read the result. Use after a merge, when asked to apply, rerun or deploy something, or when a run fails.
---

# Running a workflow

Nothing is applied from a laptop. Every change reaches the lab through a
numbered workflow, dispatched with `gh` and only when the user asked for the
deploy. Check first, read it, then apply.

## Which run, for which change

| changed | run, in order |
|---|---|
| a machine in `infra/stacks/<stack>/machines.auto.tfvars` (new, resized, a `builder` option, its `services` list) | `03` plan, read it, `04` apply; then the `05` playbook the option belongs to |
| a brand-new machine | `04`, then `05` `harden` with `bootstrap=true` and `limit=<name>` before any other `05` run |
| the VM baseline (`harden.yml`, its roles) | `05` `harden` |
| a container service: template, defaults, catalog | `05` `services`, `limit=<host>` |
| a name, a port, a route, `pocketid-clients.json` | `05` `ingress` (always `environment=lab`: horizon is there) |
| `infra/stacks/cloudflare/` | `10` plan, then apply |
| `roles/observability-*`, `playbooks/observability.yml` | nothing: it applies on merge. Hosts in `edge` or `qnta` still need a dispatched `05` `observability` for that environment |
| `infra/tailscale/policy.hujson` | nothing: `06` tests on the pull request and applies on merge |
| a hypervisor (`playbooks/proxmox.yml`, `roles/proxmox-*`) | `07` |
| the NAS (`playbooks/nas.yml`, `roles/nas-*`) | `12` |
| a workstation (`playbooks/workstation.yml`, `inventories/workstations`) | `13`, while the desktop is on |
| a mount in a machine's `builder.storage` | `04`, then `05` `storage` |
| Docker on a machine (`docker_enabled`) | `04`, then `05` `docker`, then `05` `docker-management` |

`environment` is the Stack the machine is in: `lab` (xps-pve: jwst, ark,
horizon, sputnik), `edge` (zima-pve: nebula, magnetosphere, aurora), `qnta` (the
tenant). `05` cannot see a machines-map change until `04` has applied it.

## The inputs

| workflow file | inputs | the word that applies |
|---|---|---|
| `03_opentofu-plan.yml` | `environment` | plans only |
| `04_opentofu-apply.yml` | `environment`, `confirm` | `apply` |
| `05_ansible-builder.yml` | `environment`, `playbook`, `limit`, `tags`, `bootstrap`, `force_reboot`, `confirm` | `apply`; anything else is check mode |
| `07_proxmox-node.yml` | `playbook` (`proxmox`, `reboot`, `audit`), `limit`, `tags`, `bootstrap`, `confirm` | `apply`; `reboot` for the reboot playbook |
| `08_pbs-backup.yml` | `vm`, `confirm` | `BACKUP` |
| `09_pbs-restore.yml` | `vm`, `mode`, `snapshot`, `confirm` | `RESTORE` |
| `10_cloudflare.yml` | `confirm` | `apply`; default plans |
| `12_nas.yml` | `action`, `project`, `confirm` | `apply` |
| `13_workstation.yml` | `limit`, `tags`, `confirm` | `apply`; fails fast with "not on the tailnet" when the desktop is off |
| `02_packer-build.yml` | `template`, `node`, `force_rebuild` | runs when dispatched |
| `99_opentofu-destroy.yml` | `environment`, `confirm` | `DESTROY`: only on the user's explicit word, naming the Stack |

`07`'s `bootstrap` defaults to **true** (connect as root, for a node's first
run). Pass `-f bootstrap=false` on every later run.

## Steps

1. Dispatch the check, from `main`:

   ```
   gh workflow run 05_ansible-builder.yml --ref main -f environment=lab -f playbook=ingress -f confirm=check
   ```

2. Find and follow it. Done when it exits 0.

   ```
   id=$(gh run list --workflow 05_ansible-builder.yml --limit 1 --json databaseId -q '.[0].databaseId')
   gh run watch "$id" --exit-status
   ```

3. Read what it would change: `gh run view "$id" --log | grep -E 'changed:|would|failed|fatal'`
   and the recap at the end. Tell the user what will change in one or two
   lines. An unexpected `changed` is a reason to stop and look.
4. Dispatch again with the applying word. Follow it the same way.
5. Run the proof the task skill names. A green run is not the proof.

## When a run fails

| in the log | cause | fix |
|---|---|---|
| `SSH readiness failed for gitops@<name>: failed to look up local user "gitops"` | a new machine never had its bootstrap run; it blocks every host | `05` `harden`, `bootstrap=true`, `limit=<name>` |
| `Type apply in the confirm input` | the confirmation word was wrong | dispatch again with the word from the table |
| a tenant VM unreachable over Tailscale | correct: tenant hosts are reached through the node | see `docs/gitops/tenants.md`, "Things that will mislead you" |
| `Pocket ID ... HTTP 401` | `POCKETID_API_KEY` expired | by hand: `pocket-id` |
| check mode fails on a host that has never been applied | a task reads a file the apply would create | apply once with `limit=<host>`, or add the stat guard the role's other tasks use |
| `Pocket ID GET failed with HTTP 404` after an `ingress` apply whose Ansible recap is clean | Traefik restarted for a route change and the login service was briefly unreachable through it | `gh run rerun <id> --failed` |
| `API rate limit exceeded` in a CI job | GitHub limited the runner's address | re-run the job later |

## Guardrails

- One apply at a time per Stack: state is locked, and a second run waits or fails.
- A run that touches every host (`limit=all` on `harden`, `updates`,
  `reboot`) is named to the user before it starts.
