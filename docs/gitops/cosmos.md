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

A merge to COSMOS `main` releases itself:

1. **COSMOS CI** runs `npm run check` and builds both images. On a push to
   `main` that passes, its `release` job takes a short-lived token from the
   **COSMOS release** GitHub App and dispatches **Release COSMOS** here with
   the commit SHA. The app is installed on AUTOLAB only and has one
   permission, Actions read and write: it can start workflows here and
   nothing else. Its Client ID is the COSMOS variable
   `COSMOS_RELEASE_APP_CLIENT_ID`, its private key the COSMOS secret
   `COSMOS_RELEASE_APP_KEY`.
2. **Release COSMOS** (`cosmos-release.yml`) runs three jobs in order:
   - **publish** calls "Publish COSMOS images" (`cosmos-publish.yml`). It builds
     both images on the runner *before* joining the tailnet, so Dockerfile
     `RUN` steps never execute with a route to the lab, and refuses to
     overwrite an existing tag (`<sha>-<run id>-<attempt>`).
   - **pin** opens a pull request that changes `autolab_services_cosmos_image_tag`
     in `roles/container-services/defaults/main.yml`, and merges it. Same rule
     as every image in this lab: a version bump is a diff. This needs the
     repository setting "Allow GitHub Actions to create and approve pull
     requests".
   - **deploy** runs `05 - Ansible Builder`, playbook `services`, limit `jwst`,
     `confirm: apply`, and waits for it. The role verifies that the gateway
     refuses a direct request and that an authenticated one reaches the API
     *and* the database.

One release runs at a time; a newer one waiting replaces an older one that has
not started. To release by hand, or to roll back, run Release COSMOS with any
commit on COSMOS `main`. "Publish COSMOS images" still runs alone when only the
images are wanted.

Rollback is a release of an older commit, or a pin pull request with the previous tag followed by the services playbook. The registry keeps every tag. The
database does not roll back with the code: while COSMOS has no migrations that
does not matter, and once it does, a release that changed the schema must be
backward compatible for one version.

The web bundle inside the gateway image and the **installed iPhone app are
different things**. The deploy job updates what a browser or home-screen web app loads.
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
- The release app can start *any* workflow here, Apply and Destroy included,
  because GitHub has no per-workflow permission. Its key therefore lives in the
  COSMOS `release` environment, which only `main` may use, so a branch or a
  pull request cannot read it. Anyone who can push to COSMOS `main` can deploy
  COSMOS, and whoever holds the key can dispatch lab workflows: both are the
  owner alone today.
- Mitigations in place: the publisher refuses any ref but AUTOLAB `main` and
  takes only commits on COSMOS `main`; builds run before the tailnet connection; the COSMOS checkout uses a
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
