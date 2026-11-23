---
tags: [gitops, nebula, apps, nas, nfs, backups, edge]
status: draft
audience: operator
---

# nebula — where the apps run

`nebula` is a VM on zima-pve (edge Stack, VMID 302, 4 vCPU, 6 GB, 80 GB on the
HDD). It runs what people use: [Forgejo](forgejo.md), [AdventureLog](adventurelog.md) and the [self-hosted apps](apps.md).
What the lab runs for itself (Dockhand, the registry, the editor, Diun) stays
on jwst.

## Why not jwst

| | jwst | nebula |
|---|---|---|
| RAM | 7.5 GB, shared with Prometheus, Loki, Grafana and a 3 GB editor | 6 GB for the apps and nothing else |
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

## Things that will mislead you

Each of these cost a fix or a wrong turn between the first design and a working
deploy. They are recorded because each looked like something else.

**A test that builds its own input proves the test.** The database backup passed
every local run with a hand-written config, and the rendered config silently
dropped `kind`, so LinkAce's MariaDB would have been dumped with `pg_dump` (#263).
Test the file the role actually renders. `scripts/test_db_backup_config.py`
does.

**A setting that is not in the workflow's extra-vars never reaches Ansible.**
The workflow turns repository secrets into one JSON of role variables, and the
five Pocket ID client pairs were wired into the environment but not into that
JSON, so every app deployed with no login (#261). Nothing fails: the role simply
sees an empty client and skips Pocket ID.
`scripts/test_workflow_extra_vars.py` now fails when a role variable ending in
`_oidc_client_id`/`_secret` has no entry in the workflow.

**Some apps answer 400 to the tailnet name.** Tandoor (`ALLOWED_HOSTS`) and
LinkAce refuse a request whose `Host` is `nebula.<tailnet>:810x`, so a monitor or
healthcheck that dials the machine by name reports a healthy app as down. Dash
checks use the public `<app>.lab.<zone>` name (#264); the containers' own
healthchecks send their public `Host` (LinkAce) or list `127.0.0.1` in
`ALLOWED_HOSTS` (Tandoor).

**Healthcheck tools differ by image.** Sure has `curl` and no `wget`; LinkAce
and Tandoor have `wget`, and LinkAce's busybox `wget` mishandles a `Host`
header, so it uses `curl`. AdventureLog has neither and uses Python. Look in the
image before writing the check, and read `docker inspect` health output when a
container is "unhealthy" for no visible reason.

**Mounting a share that is not there writes to the local disk.** `hard` NFS and
Docker's restart policy race at boot: containers start before the mount, and
Docker will happily create the missing source directory on the VM's disk, so uploads
land where the NAS will never see them. The service refuses to run without
the mount, its bind mounts use `create_host_path: false`, and the boot unit
`RequiresMountsFor` the share.

**The NAS's NFS rules can disappear on a reload.** UGOS can reload NFS while
Tailscale DNS is unavailable and omit hostname-based rules from the active
exports, so a mount that worked yesterday is refused today (#266). The NFS
export guard on the NAS notices and restores the missing rule from
`/etc/exports`; see [NAS storage](nas-storage.md).

**nebula currently shares the PBS datastore's export (#262).** The `apps` share
was not created, so nebula mounts `/volume1/autolab`, the same share that holds
the PBS datastore. A compromised app VM could delete the backups. This is a
known, temporary exposure; the cure is a separate share for the apps and a
PBS-only export for ark, planned around stopped backup jobs and a verified
restore before the old copy goes. Until then treat nebula's NFS access as access
to the backups.

**Pocket ID says emails are unverified.** Apps that match by email, or refuse
unverified ones, then misbehave in different ways. See
[Verified emails](apps.md#verified-emails).

**The first-run of each app is not the same.** LinkAce's tables do not exist
until `migrate` (the setup wizard runs it; a headless setup must). Tandoor 2 runs
allauth headless, so its classic `/accounts/oidc/<id>/login/` answers 404 and the
proof that Pocket ID is configured is its provider list. AdventureLog creates
its administrator only on the first boot (the email is baked in then) and needs
~2 GB once while it downloads region data. Sure's sign-in is a CSRF-protected
POST with `Secure` cookies, so it cannot be driven with `curl` over plain HTTP;
the page carrying the button is the proof.

**Image tags are not always the release tag.** Sure's release `v0.7.6-hotfix.1`
is the image tag `0.7.6-hotfix.1` (no `v`). Check with `docker manifest inspect`
before pinning. Forgejo's newest line (v17.0.0) shipped with a warning against
upgrading to it; the lab runs the LTS.

**Forgejo's API is partly asynchronous.** Creating a fork answers `202`, not
`201`; a bootstrap that only accepts 200/201 reports success as failure.
Pull-mirror creation is synchronous and slow for large repositories.

**Cloudflare in front of Pocket ID rejects some clients.** Scripts that call
Pocket ID's API must send a recognizable `User-Agent`; a bare Python one is
challenged (#268).

**Local testing quirks (Apple Silicon).** A Node build step in AdventureLog's
Dockerfile dies with exit 132 (illegal instruction) natively and works as
`--platform linux/amd64`, which is also what nebula is. `postgis/postgis` has no
arm64 image; `imresamu/postgis` stands in locally. In an Ansible test harness,
`vars_files` outrank play `vars`; pass test values with `-e`.

**Pocket ID needs a passkey, so a person creates what it holds.** Client
provisioning is automated through its API (see [AdventureLog](adventurelog.md)),
but the API key itself is created by hand and stored as a repository secret.
