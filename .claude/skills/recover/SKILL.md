---
name: recover
description: Rebuild or recover a lost piece of AUTOLAB - a VM, a hypervisor, PBS, Pocket ID, the NAS mount, OpenTofu state. Use after a failure, before a risky migration, or to answer "what if we lose X".
---

# Recovering what was lost

Two ways back, and the choice is per machine: **restore** it from PBS when
it holds state that is nowhere else, **recreate** it from git when it does
not. Recreating is cleaner; restoring is the only way to keep the data.

## Which way, per piece

| lost | holds | way back |
|---|---|---|
| sputnik | nothing | recreate: `new-vm` |
| jwst | metrics, logs, the registry, service data (`qr.db`, Hermes) | restore: `09`, `mode=replace`. Recreating works too and loses history and that data |
| horizon | Pocket ID's database: users, passkeys, groups, clients | restore. Recreated from nothing, everyone registers a new passkey: `docs/gitops/pocket-id.md`, "Recreating it" |
| nebula | app databases (also dumped nightly to the NAS) | restore; or recreate and load the newest dumps (`docs/gitops/nebula.md`) |
| ark | nothing: the chunks are on the NAS | recreate, then fix the storage fingerprint on the node (`docs/gitops/backups.md`) |
| a node | its guests | by hand: reinstall and bootstrap, `proxmox-node` onboarding, put the encryption key back, then restore each guest |
| the encryption key on a node | the ability to read every backup | by hand: from the password manager or R2 (`autolab-keys`). Without it the backups are noise |
| a NAS share's permissions | access for PBS and mounts | by hand: `nas`, "When a share refuses" |
| the NAS itself | every backup's chunks | there is no offsite copy yet. Say so plainly |
| OpenTofu state | what exists, by resource | it is in R2, versioned: `docs/gitops/05-r2-state-backend.md` |
| a GitHub secret | one credential | regenerate at its source: `secret` |

## Steps

1. Name what is lost and what it held, from the table. Tell the user which
   way back you propose and what will not come back.
2. Stop writers first: a half-dead machine that still holds a Tailscale
   identity or a database should be off before its replacement is on.
3. Restore: `backup-restore`, "Restore for real". Recreate: `new-vm`, then
   every playbook its `builder` block implies, in order.
4. A recreated or restored VM can have a new tailnet address: NAS export
   rules keyed to the old one are redone by hand (`nas`).
5. `prove`: the services answer, home is green, and a backup of the new
   machine completes (`08`).
6. `record-decision` when the recovery showed a gap: the gap goes in the
   concern's page, under what will mislead you.

## Before a risky migration

`08` for the guests involved, then `09` in `test` mode for at least one, so
the way back is proven before it is needed.

## Guardrails

- `mode=replace` and anything that destroys are the user's explicit word.
- Never regenerate or delete an encryption key to "reset" something.
