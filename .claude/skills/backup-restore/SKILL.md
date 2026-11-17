---
name: backup-restore
description: Back up a guest now, prove a backup restores, restore for real, or find why a backup failed in AUTOLAB. Use before a risky change, on a "Backup is missing" alert, or when something must be recovered.
---

# Backups and restores

The design, state and traps: `docs/gitops/backups.md`. Each node backs up
its guests to PBS on ark at 02:00; the chunks are on the NAS, encrypted
with a key that lives on the node, in the password manager and in R2.

## Back up now

`run-workflow`: `08`, `vm=<name>` or `all`, `confirm=BACKUP`. It uses the
nightly job's own settings. A guest asked for by name is backed up even
when the nightly excludes it. Done when the run reports the guest's backup
finished.

## Prove a restore

`09`, `vm=<name>` or `all`, `mode=test`, `confirm=RESTORE`. It restores the
newest snapshot to a new guest with its network link down, waits for the
guest agent, records the OS it reports, and destroys it. Done when the
summary has `RESTORE RESULT <name>: BOOTED as <os>`.

Run it for `all` after any change to the backup path, and monthly.

## Restore for real

`mode=replace` stops the live guest and restores over it. One guest, named,
and only on the user's explicit word.

1. Any other value in `confirm` lists the snapshot that would be used and
   stops. Run that first and show the user which snapshot it is.
2. `09`, `vm=<name>`, `mode=replace`, `snapshot=<that one or empty for the
   newest>`, `confirm=RESTORE`.
3. Done when the guest is running, answers on the tailnet, and its services
   are green on home.

A database on nebula is usually better restored from its nightly dump than
by rolling back the whole VM: `docs/gitops/nebula.md`, "Database backups and
restores".

## A backup failed

1. `07`, `playbook=audit`, `bootstrap=false`. It reads recent backup errors
   on every node and PBS's task logs, and changes nothing.
2. Match what it shows:

   | it shows | cause |
   |---|---|
   | `backup connect failed: http request timed out` for ark | ark is in its own job; it belongs in the job's `exclude` |
   | permission denied on the datastore | UGOS rewrote the share's ACLs when a permissions dialog was saved; the fix is by hand on the NAS (`nas`) |
   | the storage is offline after ark was rebuilt | PBS has a new certificate: update the fingerprint (`docs/gitops/backups.md`) |
   | *Backup collector is stale* | the collector on jwst, not the backups: check its timer |

3. Fix, then `08` for the affected guest. The alert clears on the next
   collection after a good backup.

## Guardrails

- The encryption key file on the node is never deleted or regenerated.
  Without it every backup is noise.
- Raising the alert's age limit does not repair a failed backup.
