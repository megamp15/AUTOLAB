---
tags: [gitops, cosmos, registry, pocket-id, services]
status: draft
audience: operator
---

# COSMOS

The owner's personal hub (the app lives in the COSMOS repository). AUTOLAB
runs it as a container service on jwst, publishes its images from CI, and puts
it behind the passkey login. Nothing here is public.

```
iPhone / browser ──▶ cosmos.lab.<zone> ──▶ horizon: Traefik + Pocket ID (admins only)
   on the tailnet                              │  adds X-Autolab-Cosmos-Token
                                               ▼
                       jwst :8105  cosmos-gateway (nginx: web build, /api proxy)
                                               │  internal Docker network, no route out
                                  cosmos-api ──┴── cosmos-db (Postgres 17)
```

| container | does | reachable from |
|---|---|---|
| `cosmos-gateway` | serves the web build, proxies `/api/`, refuses any request without Traefik's token (403) | jwst's tailnet address, port 8105 |
| `cosmos-api` | Fastify API; read-only filesystem, no capabilities, uid 1000 | the gateway only |
| `cosmos-db` | Postgres 17 on the named volume `cosmos-data` | the API only |

Defined in `roles/container-services/templates/services.d/cosmos.yml.j2`. The
port and the `admin` login (Pocket ID `admins` group) are in the service
catalog in `playbooks/group_vars/all.yml`, so the Traefik route appears when
the service is enabled, the same way Dockhand's does.

## Secrets: where each one lives

| secret | made by | lives | never in |
|---|---|---|---|
| database password, proxy token, MCP token | the services role, once, `openssl rand -hex 32` | `/etc/autolab/cosmos/` on jwst (`0700` root); each container's env file is `0600` and holds only what that container uses | GitHub, git, logs |
| proxy token handoff to horizon | the ingress role reads it over SSH and writes it into Traefik's dynamic config | horizon, `0600` | the browser; the web bundle |
| `COSMOS_DEPLOY_KEY` | you, once: an SSH key pair, public half added to the COSMOS repo as a **read-only deploy key** | GitHub secret on AUTOLAB (`lab` environment) | the COSMOS repo (the private half) |

Re-running the playbook never rotates a generated secret (`creates:`), so it
cannot desync the database password from the data directory. To rotate the
proxy token, delete its file and run the `ingress` and `services` playbooks in
that order, then check the gateway answers 403 without it.

The MCP token exists because the API refuses to start without one. It is not
yet reachable from outside: how a local MCP process gets to the API is a
decision for the MCP increment (see the COSMOS repo's `docs/deployment.md`).

## Releasing: build, publish, pin, deploy

Four separate steps, each with its own control:

1. **Merge COSMOS work to `main`** in the COSMOS repo. CI there runs
   `npm run check` and builds both images.
2. **Run "Publish COSMOS images"** (`cosmos-publish.yml`, manual, AUTOLAB
   `main` only) with the full commit SHA. It builds both images on the runner
   *before* joining the tailnet, so Dockerfile `RUN` steps never execute with a
   route to the lab. Only the registry steps then run on the tailnet. It
   refuses to overwrite an existing tag. The tag
   (`<sha>-<run id>-<attempt>`) is printed in the job summary.
3. **Pin it**: a pull request changes `autolab_services_cosmos_image_tag` in
   `roles/container-services/defaults/main.yml`. Same rule as every image in
   this lab: a version bump is a diff.
4. **Deploy**: after the merge, run `05 - Ansible Builder`, playbook
   `services`, `confirm: apply`. The role verifies that the gateway refuses a
   direct request and that an authenticated one reaches the API *and* the
   database.

Rollback is step 3 with the previous tag. The registry keeps every tag. The
database does not roll back with the code: while COSMOS has no migrations that
does not matter, and once it does, a release that changed the schema must be
backward compatible for one version.

The web bundle inside the gateway image and the **installed iPhone app are
different things**. Step 4 updates what a browser or home-screen web app loads.
A future Capacitor build carries its own copy of the UI and changes only when
a new native build is installed. See the COSMOS repo.

## Backups

- **Daily logical dump** at about 01:15 (`autolab-cosmos-dump.timer`): `pg_dump
  --format custom`, checked readable with `pg_restore --list` before it gets its
  final name, newest 14 kept in `/opt/autolab/services/cosmos/dumps`.
- **Nightly Proxmox backup** (02:00) of jwst carries the dumps and the volume to
  PBS on the NAS. Do not put the live Postgres data on NFS or SMB.
- **Not yet covered:** an alert when a dump fails (only `systemctl status
  autolab-cosmos-dump` shows it), and a restore rehearsal for COSMOS data.
  Restore with `pg_restore --clean --if-exists --dbname` into the `cosmos-db`
  container. Do the rehearsal before the first personal record goes in.

## Accepted risk: single-owner tailnet

Recorded 2026-11-08, accepted by the owner.

- AUTOLAB `main` has no branch protection, and `tag:ci-runner` can reach the
  whole tailnet. Anyone who can push to AUTOLAB `main` can run workflows with
  that reach.
- That is acceptable because the owner is the only writer. It stops being
  acceptable the moment a second person or an untrusted automation can write to
  AUTOLAB `main`: revisit it then, starting with branch protection and a
  narrower tag for CI.
- Mitigations in place: the publisher is manual-dispatch and refuses any ref but
  `main`; builds run before the tailnet connection; the COSMOS checkout uses a
  read-only deploy key; the app and API are reachable only on the tailnet, behind
  Pocket ID `admins` plus the proxy token.
- GitHub's `lab` environment should be limited to the `main` branch. Check what
  else uses `lab` before turning that on: plan/apply workflows that run on pull
  requests would be blocked too.

## Bringing it up, in order

1. Commit and push COSMOS to GitHub `main`. CI is green. (Done 2026-11-16.)
2. Create the deploy key pair, add the public half to COSMOS (read-only) and the
   private half as `COSMOS_DEPLOY_KEY`. Never paste either in chat. (Done
   2026-11-16: deploy key "AUTOLAB cosmos-publish (read-only)".)
3. Merge the AUTOLAB pull request that adds this service, the route and the
   workflow. Nothing deploys: `cosmos` is not yet in jwst's list and the image
   tag is empty.
4. Check jwst's headroom with an authorized account (`docker stats`, `free -m`).
   The VM has 7.5 GB and code-server is capped at 2 GB. COSMOS needs roughly
   300 to 500 MB.
5. Run "Publish COSMOS images" with the commit SHA from step 1.
6. Second pull request: set `autolab_services_cosmos_image_tag` and add `cosmos`
   to jwst's `services` list. Merge it and run `04 - OpenTofu Apply` for `lab`
   (the machines map changed). Then run `05` with `services` first, because it
   generates the proxy token, and with `ingress` second, because it reads that
   token to build the route.
7. Open `https://cosmos.lab.<zone>` on a tailnet device: Pocket ID login, then
   the COSMOS shell.

## What was and was not proven

Proven locally against the rendered Compose file: all three containers start
under the hardening above; the gateway returns 403 without or with a wrong
token, 200 with it, `/api/status` reports the database connected, and
`/api/mcp/status` needs its own bearer; the API has no route to the internet;
only the gateway publishes a port; the dump script produces readable dumps
and prunes to the newest N.

Not yet proven: anything on jwst or horizon, the Traefik route, the publish
workflow, pulling from `registry.lab.<zone>`, and jwst's memory headroom.
