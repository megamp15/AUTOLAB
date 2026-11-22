---
name: service
description: Add, change, move or remove a container service in AUTOLAB (a compose service on jwst, nebula or another Docker host). Use for a new app, a version bump, a port or login change, or retiring one.
---

# A container service

How services work: `docs/gitops/services.md`. Apps on nebula:
`docs/gitops/apps.md` and `docs/gitops/nebula.md`. Every place a service is
written down: `docs/gitops/definition-of-done.md`.

## Adding one

1. **Where**: lab tooling on jwst (`lab`), apps a person uses on nebula
   (`edge`). The host needs `docker_enabled`; a new host is `new-vm` first.
2. **The container**: `roles/container-services/templates/services.d/<name>.yml.j2`.
   Copy the nearest neighbour. The house shape:
   - image pinned to an exact version in `autolab_services_images`;
   - published ports bound to the tailnet address
     (`{{ autolab_services_tailscale_ip }}:<port>:<inner>`), never `0.0.0.0`:
     Docker's rules sit ahead of ufw's;
   - `read_only`, `cap_drop: [ALL]`, `no-new-privileges` when the app
     allows it; a healthcheck;
   - a `dockhand.tags` label naming the app, the same on its database and
     workers, so Dockhand groups them (`docs/gitops/docker-management.md`);
   - data under `{{ autolab_services_root }}/<name>/`; a database on the
     host's disk, files that must outlive the VM on the NAS mount.
3. **The catalog**: `autolab_service_catalog` in
   `playbooks/group_vars/all.yml`: its `port` and its `login`.

   | `login` | when |
   |---|---|
   | `plugin` | the app has no login of its own: the passkey sits in front |
   | `admin` | the same, `admins` only, plus a token only Traefik holds |
   | `own` | the app keeps a user per person and signs them in with Pocket ID |
   | `none` | not a browser (a registry, an agent), or no HTTP port at all |

   Pick a port no service has had, so a stale route cannot land on the wrong app.
4. **Turn it on**: add the name to the machine's `builder.services`. A
   machine outside `lab` is also named in `autolab_remote_services`.
5. **Secrets**: generated on the host when they only protect its own data;
   otherwise `secret`.
6. **Sign-in**: `login: own` gets a client in
   `templates/managed-pocketid-policy.json.j2`; the run creates it. `pocket-id`.
7. **Its name**: `<name>.lab.<zone>` appears from the catalog with no edit.
   A public name is `route`.
8. **Backups**: a Postgres is picked up by `autolab-db-backup` when declared
   in `autolab_services_databases`; state in a file needs a line in
   `docs/gitops/backups.md` saying where it is and what holds a copy.
9. `observe`: containers report by themselves; add a scrape or a rule only
   for something worth it.
10. `surfaces`, then `pull-request`.
11. `run-workflow`: `03`/`04` for the Stack (the services list is in the
    map), `05` `services` with `limit=<host>`, then `05` `ingress`
    (`environment=lab`) for the name.

## Proof

- `https://<name>.lab.<zone>` opens, after the passkey or the app's own
  sign-in; signed out, `curl` gets 401 or the app's login page.
- From a machine off the tailnet the name does not resolve.
- The container is `healthy`, its card on home is green, its tile is on dash.

## Changing one

| change | edit | run |
|---|---|---|
| version | the pin in `autolab_services_images`; read the release notes for migrations first | `05` `services` |
| port or login | the catalog | `05` `services`, then `05` `ingress`; then `surfaces` |
| our own patch to an upstream app | fork in Forgejo, `autolab_services_sources.<name>` `mode: fork` (`docs/gitops/apps.md`) | `05` `services` |
| move to another machine | the name out of one `services` list and into another; move its data first | `04`, `05` `services` on both, `05` `ingress` |

## Removing one

The name out of the `services` list; the run drops the container
(`remove_orphans`). Volumes and `/etc/autolab/<name>*.env` stay until
deleted by hand: say where they are in the pull request. Its Pocket ID
client is deleted by the next services run. Then `surfaces`, read as a list
of places to delete from.

## Guardrails

- A stack made in Dockhand's UI is in no file and the next run overwrites
  it. Dockhand is for operating, the template is for defining.
- A container reachable through a tunnel has no admin page in it. Public
  and admin faces are separate containers on separate networks
  (`docs/gitops/qr.md` is the worked example).
