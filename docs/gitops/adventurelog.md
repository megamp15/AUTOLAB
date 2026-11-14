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

One-time, by hand, because Pocket ID is signed into with a passkey:

1. Pocket ID → *OIDC Clients* → *Add*: name `adventurelog`, callback URL
   `https://adventurelog.lab.<zone>/accounts/oidc/pocketid/login/callback/`
   (trailing slash included). Under *Allowed User Groups* choose who may sign
   in. Save, open it, *Generate* the secret.
2. Repository secrets `ADVENTURELOG_OIDC_CLIENT_ID` and
   `ADVENTURELOG_OIDC_CLIENT_SECRET`; repository variable
   `APPS_ADMIN_EMAIL`, **the email of your Pocket ID user**. The app
   makes its administrator from it on the first boot, and a Pocket ID sign-in
   with the same email is attached to that account rather than creating a
   second one. It is read once; later it is changed in the Django admin.
3. Workflow **05**, playbook `services` (check, then `confirm: apply`). The
   first run takes several minutes: migrations, then the world's regions. The
   playbook then registers Pocket ID as a login inside the app and **opens the
   sign-in URL**, failing if the app cannot reach Pocket ID's discovery
   document. Then playbook `ingress`, so Traefik has the route.
4. Open `https://adventurelog.lab.<zone>` → *Pocket ID*.

Pocket ID is registered in the app by `files/adventurelog/pocketid_provider.py`,
because AdventureLog keeps login providers in its database and has no
environment variable for them. It is idempotent and reports `CHANGED` only when
something differed, so rotating the client secret is: change the GitHub secret,
rerun `services`.

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
2. AdventureLog → your profile → *Settings* → *Immich Integration*. Server URL
   `http://singularity.<tailnet>:2283/api` (the playbook prints it); paste the
   key; *Connect*.

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
