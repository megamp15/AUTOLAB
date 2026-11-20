# ADR-0008: The apps run on nebula; their files are on the NAS and their databases are not

## Status

Accepted — 2026-11-14

## Context

The lab was to host a travel log (AdventureLog), recipes (Tandoor), a flight log
(AirTrail), bookmarks (LinkAce), personal finance (Sure) and its own git host
(Forgejo), all signed into with Pocket ID, all integrated with the NAS and
Immich, all reproducible from this repository, and all changeable: if an app has
a bug, or upstream disappears, the code must be ours to fix.

Three places could host them. The NAS runs Immich in UGOS's own Docker by hand,
which is not in git. jwst runs the lab's tooling from the machines map, but has
7.5 GB shared with Prometheus, Loki, Grafana and a 3 GB editor, sits on a
hypervisor that is Wi-Fi only (a silent September outage), and had already
OOM-killed its neighbours sixteen times during builds. zima-pve is wired and had
about 14 GB free.

State had two candidates too: everything on the NAS, as asked, or databases
local. This lab's own storage notes say SMB is wrong for live databases, and the
NAS serves NFS v3 only, whose locking is weak. A Postgres data directory on NFS
v3 is fine until the link blips, then corrupts or hangs.

## Decision

1. **A VM of its own, `nebula`, on zima-pve** (edge Stack), takes the apps and
   Forgejo. jwst keeps the lab's own tooling. A service moves by changing a line
   in a machines map, and a test keeps the ingress's list of remote services equal
   to it.
2. **Files on the NAS over NFS** (uploads, repositories, settings); a service that
   keeps files there refuses to start without the mount.
3. **Live databases on the VM's disk**, dumped nightly to the NAS and restored
   weekly into a throwaway container of the same image, which must match
   production's table count. The VM is also backed up by PBS.
4. **Code we hold.** Forgejo keeps pull mirrors of upstream and our forks; an app
   can be built from a fork at a pinned commit instead of pulling the project's
   image.
5. **Identity is Pocket ID**, one client per app, restricted to a group; the apps'
   password logins stay until a Pocket ID sign-in is proven.

## Consequences

- Losing nebula loses no files, and loses at most a day of database changes.
- A backup is only believed once it has been restored; the restore test and its
  alerts are part of the design, not an addition.
- nebula's NFS access is, for now, access to the PBS datastore's share
  (see [nebula](../gitops/nebula.md#things-that-will-mislead-you)). Closing that
  needs a separate share for the apps and a PBS-only export.
- Two database engines are in use (LinkAce is on MariaDB, as its project
  documents); the backup script handles both.
- Each app trusts email differently, so Pocket ID's verified-email setting is a
  policy, not a detail ([apps](../gitops/apps.md#verified-emails)).
