---
tags: [gitops, forgejo, git, mirrors, forks, pocket-id, nebula]
status: active
audience: operator
---

# Forgejo

The lab's git host, on [nebula](nebula.md) at `forgejo.lab.<zone>` (tailnet
only). It exists so that **the apps are built from code we hold**: if a project
is changed, abandoned or taken down upstream, nothing here notices, and if one
of them needs a fix, the fix is a commit.

Forgejo, not GitLab: it idles near 100 MB where GitLab wants 4 GB, and it is
on Pocket ID's list of supported clients. Pinned to the long-term-support line.

## Two organizations

| org | what | changed by |
|---|---|---|
| `mirrors` | **pull mirrors** of the upstream projects, refreshed every 8 h | nobody — it follows upstream |
| `apps` | **our forks**, made once from a mirror and ordinary repositories after that | us |

`mirrors/<x>` is the pristine copy and the place to read what upstream did.
`apps/<x>` is where changes go. To take upstream's fix into a fork: open a pull
request in `apps/<x>` from `mirrors/<x>`, or merge it locally.

Both are declared in `container-services` defaults
(`autolab_services_forgejo_mirrors`, `_forks`) and created by
`autolab-forgejo-bootstrap`, which creates what is missing and never touches
what exists. A fork's history is never reset by a rerun.

## Where it lives

Repositories, packages and settings (`app.ini`) are on the NAS, in
`/mnt/apps/forgejo/data`: the rootless image, which the Forgejo docs recommend
for repositories on NFS, on a `hard` mount. The database is local and is dumped
nightly and restore-tested weekly like every app's (see [nebula](nebula.md)).

`app.ini` holds the database password and secret key, so the NAS share
holds them. The NAS is yours and the share is only for this VM; if that is not
acceptable, move `FORGEJO__security__SECRET_KEY` out of the env file only after
reading Forgejo's notes on rotating it.

## Setting it up

1. Pocket ID → *OIDC Clients* → *Add*: name `forgejo`, callback URL
   `https://forgejo.lab.<zone>/user/oauth2/PocketID/callback` (the source is
   registered as `PocketID`; that name is in the URL, so keep it). Allowed
   groups as you like. Generate the secret.
2. Secrets `FORGEJO_OIDC_CLIENT_ID`, `FORGEJO_OIDC_CLIENT_SECRET`; the variable
   `APPS_ADMIN_EMAIL` (the email of your Pocket ID user) is shared by every app.
3. Workflow **05**, environment `edge`, playbook `services`. It starts Forgejo,
   makes a break-glass administrator `forgejo-admin`, registers Pocket ID,
   **opens the sign-in URL and fails if it does not reach Pocket ID**, makes
   the orgs, the mirrors and the forks. Then playbook `ingress` on `lab` for the
   route.
4. Sign in with Pocket ID. Anyone in Pocket ID's `admins` group is a Forgejo
   site administrator on sign-in; everyone else an ordinary user.

The break-glass password:
`ssh megamp15@nebula sudo grep FORGEJO_ADMIN_PASSWORD /etc/autolab/forgejo.env`.
Once a Pocket ID sign-in works, set
`autolab_services_forgejo_password_login: false` in a pull request.

## Changing an app (the point of all this)

1. Edit in `apps/<app>` (clone from `https://forgejo.lab.<zone>/apps/<app>.git`
   in code-server, or on a laptop on the tailnet; write access is a
   Forgejo token), and push a commit.
2. In `container-services` defaults, `autolab_services_sources.<app>`: set
   `mode: fork` and `ref:` to that commit (a tag or a SHA).
3. Run `services`. nebula checks the fork out at that ref, builds the image on
   the host, tags it with the commit, and recreates the container. Back to the
   project's own image: `mode: upstream`.

Building takes minutes and a few GB of RAM; nebula has room, jwst did not.

## Not done

- **SSH** is off (HTTPS clones and pushes with a token suffice on a tailnet).
- **Actions** (CI) is off. Builds happen on the host.
- Forgejo's own backups are the database dumps plus the NAS holding the
  repositories; a repository on the NAS is also inside the NAS's offsite backup.
