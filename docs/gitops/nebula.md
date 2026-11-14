---
tags: [gitops, nebula, apps, nas, nfs, backups, edge]
status: draft
audience: operator
---

# nebula — where the apps run

`nebula` is a VM on zima-pve (edge Stack, VMID 302, 4 vCPU, 8 GB, 80 GB on the
HDD). It runs what people use: [Forgejo](forgejo.md), [AdventureLog](adventurelog.md) and the [self-hosted apps](apps.md).
What the lab runs for itself (Dockhand, the registry, the editor, Diun) stays
on jwst.

## Why not jwst

| | jwst | nebula |
|---|---|---|
| RAM | 7.5 GB, shared with Prometheus, Loki, Grafana and a 3 GB editor | 8 GB for the apps and nothing else |
| Wire | xps-pve, Wi-Fi only; a September outage was a silent Wi-Fi stall | zima-pve, wired |
| NAS mounts | `hard` NFS over Wi-Fi hangs the VM when the link stalls | wired |
| Builds from source | already OOM-killed neighbours sixteen times | has the room |

## What is where

| thing | where | why |
|---|---|---|
| uploads, repositories, source checkouts | NAS, `/mnt/apps` (share `/volume1/autolab`, NFS) | outlive the VM |
| **live Postgres data** | this VM's disk (docker volumes) | a database on NFS v3 corrupts or hangs when the link blips; `nas-storage.md` already says so about SMB |
| nightly database dumps | NAS, `/mnt/apps/backups/<service>/` | the copy that survives losing the VM |
| the whole VM | PBS, nightly like every guest | the other copy |

The app VM temporarily has write access to the same export as the PBS datastore.
Move PBS into a separate share and restrict its export to ark. Plan the cutover
around stopped backup jobs, preserve the existing datastore until the new mount
is verified, and verify a restore before removing the old copy. Then restrict
nebula's access to the app share. The PBS offsite copy is not yet configured.

A service that keeps files on the NAS refuses to run while the share is not
mounted, and its container mounts use `create_host_path: false`: a missing
path is an error, never an empty directory made on the local disk. The boot unit
`RequiresMountsFor` the share.

## Database backups and restores

Every service with a Postgres gets, from `container-services`:

- `autolab-db-backup dump`, nightly 01:15: `pg_dump -Fc` into
  `/mnt/apps/backups/<service>/`, the archive's table of contents read back to
  catch truncation, then pruned (newest 14, plus Sundays for 60 days).
- `autolab-db-backup restore-test`, Sundays 04:00: restores the newest dump
  into a **scratch container of the same image** and requires the same table
  count as production. A dump nobody has restored is a hope.
- metrics for both, and three alert rules: *An app database has no recent dump*
  (36 h), *An app database dump does not restore*, *App database restores are
  not being tested* (9 d).

The first run of the playbook takes a dump and restores it before reporting
success. To restore for real, stop the service, load the newest dump with
`pg_restore --clean --if-exists` into its database container, start it.

## Standing it up (in order)

1. **NAS, in UGOS.** Use the existing `autolab` share. UGOS rewrites ACLs
   when a permissions dialog is saved; check access afterwards.
2. Merge, then workflow **04** (`confirm: apply`, environment `edge`) creates
   the VM. Workflow **05**, environment `edge`, `harden` with `bootstrap: true`
   for the first run, then `docker`.
3. **NAS export rule**, by hand: shared folder `autolab` → NFS permissions → the
   host `nebula` (by tailnet name, like ark's), read/write, **No mapping**.
4. Workflow **05**, environment `edge`: `storage`, then `docker-management`
   (Hawser agent, registered in Dockhand), `observability`, then `services`.
5. Workflow **05**, environment `lab`, `ingress`: routes
   `<service>.lab.<zone>` to nebula.

## Dockhand across hosts

One Dockhand (jwst) manages every Docker host through an authenticated Hawser
agent on each, registered by Ansible through Dockhand's API. nebula joins by
being `docker_enabled` and running `docker-management` (environment `edge`).
Containers can be inspected, restarted and read from there; anything *defined*
there is outside git, and the next Ansible run overwrites it.
