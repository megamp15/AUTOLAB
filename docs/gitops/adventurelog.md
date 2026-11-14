---
tags: [gitops, docker, services, adventurelog, immich, pocket-id]
status: active
audience: operator
---

# AdventureLog

A travel log: places visited and planned, grouped into collections, with the
photos attached to each. It runs on [nebula](nebula.md) as the `adventurelog`
service of the [container services](services.md) and is reached at
`adventurelog.lab.<zone>`, on the tailnet only, like every lab name.

## Why nebula, and not the NAS or jwst

The NAS runs Immich in UGOS's own Docker, by hand: a service there is not in
git and not rebuilt by a pull request. jwst has the RAM problem described in
[nebula](nebula.md). nebula is where the apps live; AdventureLog is one word in
its services list, and its uploads are on the NAS.

## What runs

| container | what | where its data is |
|---|---|---|
| `adventurelog` | web app, API, nginx and a cache in one image, pinned to `v0.13.1` | uploaded images on the NAS: `/mnt/apps/adventurelog/media` |
| `adventurelog-db` | PostGIS 16, no published port | volume `adventurelog-db` on nebula's disk, **dumped nightly to the NAS** and restore-tested weekly (see [nebula](nebula.md)) |

The photos attached from Immich are not copied: AdventureLog stores Immich's
asset id and asks Immich for the picture when a page is opened, so the NAS
stays the only place the originals live.

Three secrets — the database password, Django's signing key and the
break-glass admin's password — are generated on nebula the first time and kept in
`/etc/autolab/adventurelog.env` and `adventurelog-db.env` (root, `0600`). They
are not in GitHub and not in the log. To read the break-glass password:
`ssh megamp15@nebula sudo grep DJANGO_ADMIN_PASSWORD /etc/autolab/adventurelog.env`.

## Setting it up

The edge `services` playbook creates the Pocket ID client and restricts it to
`admins`. It registers the callback and configures the app, then checks the
redirect to Pocket ID. `APPS_ADMIN_EMAIL` identifies the existing local admin;
automatic email-based linking requires Pocket ID to report the email as verified.
If it is unverified, sign in to the existing local account and connect Pocket ID
from its account settings, or explicitly link the verified Pocket ID subject to
that user. Do not trust all unverified emails. Social account links live in
AdventureLog's database and are included in its database dumps.

The Pocket ID API key stays in GitHub Actions secrets. Generated client IDs and
secrets are stored on nebula in `/etc/autolab/managed-pocketid-clients.json`,
owned by root and mode 0600, and are included in the VM backup. Keep that state
when rebuilding nebula: the provisioner refuses to adopt or duplicate an
existing named client if its state is lost. Local password login stays enabled
until a Pocket ID sign-in succeeds.

Pocket ID is registered in the app by `files/adventurelog/pocketid_provider.py`,
because AdventureLog keeps login providers in its database and has no
environment variable for them. It is idempotent and reports `CHANGED` only when
something differed. Managed client secret rotation requires a coordinated
change in Pocket ID, root-only client state and the application; changing a
GitHub secret alone does not rotate a managed client.

### Pocket ID only

The password form stays on until a Pocket ID sign-in has been seen to work,
since the password is the way back in. Then set
`autolab_services_adventurelog_sso_only: true` in the role's defaults in a pull
request: the sign-in page goes straight to Pocket ID and password login is off.
Registration is closed from the start (`DISABLE_REGISTRATION`); a Pocket ID
user inside the client's allowed groups gets an account on first sign-in.

## Immich

The integration is per person, in the app, because each Immich user has their
own API key.

1. Immich → *Account Settings* → *API Keys* → *New API Key*, with permissions
   `asset.read`, `asset.view`, `album.read`, `library.read`, `user.read`.
2. For the administrator account, run `gh secret set ADVENTURELOG_IMMICH_API_KEY --env edge --repo megamp15/AUTOLAB`
   from the repository and enter the key at the prompt. Workflow **05** on edge,
   playbook `services`, validates the key's account email against `APPS_ADMIN_EMAIL`
   and creates the connection. It refuses to replace another server's integration.
3. Other users add their own keys in AdventureLog → profile → *Settings* →
   *Immich Integration*. The server URL is `http://singularity:2283/api`.

AdventureLog stores each key in its database, and database dumps contain it.
Keep both the NAS share and database backups restricted accordingly.

The URL is the NAS's tailnet name, not `immich.lab.<zone>` and not
`localhost`: the request is made by the AdventureLog container on nebula, which
reaches the NAS over the tailnet. Using
the lab name would send it round through Traefik for nothing. After this, adding
images to an adventure offers *Immich*: Smart Search or an album.

## Upgrading

Bump the tag in `defaults/main.yml`; migrations run on the app's startup. Diun
says when a newer tag exists. The project's own notes carry the version-specific
steps, and there is no way back from a migration except the PBS snapshot, so
take one first (`08 - PBS backup`).
