---
tags: [gitops, novaflix, apps, public, services]
status: draft
audience: operator
---

# Novaflix

A private tracker of what a few friends watch: each person's library of
movies and shows, filled from their streaming history. It is one of
[our own apps](own-apps.md): the code is in the Novaflix repository, and
AUTOLAB builds, pins and runs it.

The friends are not on the tailnet, so it has a public name. It keeps a user
per person and signs them in itself, so nothing sits in front of that name.

```
a friend's browser ──▶ novaflix.<zone> ──▶ Cloudflare tunnel ──▶ horizon: Traefik (no login in front)
                                                                     │
                                          jwst :8108  novaflix-gateway (nginx: web build, /api proxy)
an admin, on the tailnet                                             │
   ──▶ novaflix-admin.lab.<zone> ──▶ Traefik + passkey               │
                                          jwst :8109  novaflix-admin ┤  the same image, ADMIN_FACE=1
                                                                     ▼
                                              novaflix-server ── novaflix-db (Postgres 17)
```

| container | does | reachable from |
|---|---|---|
| `novaflix-gateway` | the public face: serves the web build, passes `/api/` to the server, answers 404 on `/api/admin/` | the tunnel, through Traefik |
| `novaflix-admin` | the same image with `ADMIN_FACE=1`: it also passes `/api/admin/` | the tailnet, behind the passkey |
| `novaflix-server` | Fastify API; read-only filesystem, no capabilities, uid 1000 | the two gateways |
| `novaflix-db` | Postgres 17 on the volume `novaflix-data` | the server only |

Defined in `roles/container-services/templates/services.d/novaflix.yml.j2`
and `novaflix-admin.yml.j2`; ports and logins in the service catalog.

## Why two gateways

There is no sign-up. An admin makes each account and resets passwords
(`/api/admin/`). A container the tunnel reaches has no admin page in it, so
those routes are answered only by a second gateway on a tailnet-only name.
The app still checks that the signed-in user is an admin; the passkey in
front is a second lock, not the only one. The services run proves both
halves: 404 from the public face, 401 from the admin face.

## What protects the public face

It answers anyone, with a sign-in page, and the app defends that itself:
salted scrypt password hashes, a session cookie whose hash is what the
database keeps, and five wrong passwords for an email from one address block
further tries for fifteen minutes. That limiter is in the server's memory, so
it resets when the container restarts.

## Secrets

| secret | made by | lives |
|---|---|---|
| database password | the services role, once, `openssl rand -hex 32` | `/etc/autolab/novaflix/db-password` on jwst (`0700` root); the two env files that carry it are `0600` |
| `NOVAFLIX_TMDB_TOKEN` | you, on themoviedb.org | GitHub secret, `lab` environment; optional |
| `NOVAFLIX_GOOGLE_CLIENT_ID`, `NOVAFLIX_GOOGLE_CLIENT_SECRET` | you, in the Google Cloud console (Google Auth Platform, a Web application client, redirect `https://novaflix.<zone>/api/auth/oidc/google/callback`, app published) | GitHub secrets; optional. Google sign-in works on the public name only, unless the admin name's redirect address is added to the same Google client |
| Pocket ID client `AUTOLAB novaflix` | the services role, with `POCKETID_API_KEY` | id and secret in `/etc/autolab/managed-pocketid-clients.json` on jwst (`0600` root). Restricted to `admins`; sends a sign-in back to the public or the admin name |
| `NOVAFLIX_DEPLOY_KEY` | you, once | GitHub secret, `lab` environment; its public half is a read-only deploy key on the Novaflix repository |

Re-running the playbook never rotates the database password (`creates:`).

## First deploy, in order

The service is defined but not enabled: `novaflix` is in no machine's
`services` list, because the role refuses to start it without a published
tag.

1. By hand: an SSH key pair; the public half as a **read-only deploy key** on
   the Novaflix repository; the private half as the secret
   `NOVAFLIX_DEPLOY_KEY` in the `lab` environment here.
2. Run **Release app** with `app=novaflix` and a commit on Novaflix `main`.
   It publishes the images and pins `autolab_services_novaflix_image_tag`.
   Its deploy job runs the services playbook, which changes nothing yet.
3. A pull request adding `"novaflix"` and `"novaflix-admin"` to jwst's
   `services` in `infra/stacks/lab/machines.auto.tfvars`.
4. `03` plan and `04` apply for the `lab` Stack; `05` `services` with
   `limit=jwst`; `05` `ingress`; `10` plan and apply for the public name.
5. Nothing by hand for the first admin: on an empty database the server
   makes an admin account for `APPS_ADMIN_EMAIL` (the email of your Pocket ID
   user), without a password. Sign in at the admin name with Pocket ID, or
   with Google if that is the same address. Everyone else is made in the
   app, under User access. An account with a password, should one be
   wanted, is still
   `docker compose --project-directory /opt/autolab/services exec novaflix-server node dist/scripts/add-user.js <email> "<name>" --admin`
   on jwst.

A push to Novaflix `main` that passes its CI releases itself: its `release`
job starts **Release app** here (`own-apps.md`, "An app that releases
itself").

## Backups

`novaflix-db` is in `autolab_services_databases`, so the shared database
dump covers it (`backups.md`), and the nightly Proxmox backup of jwst
carries the dumps and the volume.

## Proven

First deployed on 2026-11-22, by the steps above. Seen from outside the lab:

- `https://novaflix.<zone>/api/status` answers `database: connected`.
- `https://novaflix.<zone>/api/admin/users` answers 404.
- `https://novaflix.<zone>/api/auth/oidc/google` redirects to Google with the
  public callback address.
- The admin name answers 401 before the passkey.

Not yet seen: a full Google sign-in on the deployed app, and the admin name
used after the passkey.
