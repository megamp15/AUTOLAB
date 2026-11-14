---
tags: [gitops, apps, nebula, pocket-id, tandoor, airtrail, linkace, sure]
status: draft
audience: operator
---

# The self-hosted apps

Four apps on [nebula](nebula.md), beside [AdventureLog](adventurelog.md) and
[Forgejo](forgejo.md). Each is `<name>.lab.<zone>`, tailnet only, signs people in
with its own Pocket ID client, keeps its files on the NAS, and has its database
dumped nightly and restore-tested weekly.

| app | for | database | files on the NAS | idle RAM |
|---|---|---|---|---|
| `tandoor` 2.7.2 | recipes, meal plans, shopping lists | Postgres | `tandoor/media` | ~850 MB (its workers) |
| `airtrail` 3.14.0 | flights on a map | Postgres | `airtrail/uploads` | ~50 MB |
| `linkace` 2.6.3 | bookmarks, tags, link checker | **MariaDB** | none | ~75 MB + 96 MB |
| `sure` 0.7.6-hotfix.1 | accounts, budgets, net worth | Postgres | `sure/storage` | web and worker ~375 MB each |

LinkAce is on MariaDB because that is what its own compose file and docs
describe. It also runs on Postgres (checked: migrates, creates the admin, serves
its login), so one engine fewer is available if that ever matters. Its search is
the database's own; Meilisearch is a container a personal collection does not
need. Redis holds its sessions and cache.

**Sure holds financial data.** It is the one app whose sign-in page you should
not hand out. No bank aggregator or AI provider is configured: those are
credentials entered in its settings, and nothing here enters them. Sure's docs
mention product analytics that is on by default; I could not confirm the switch
that turns it off, so check its release notes (`POSTHOG_*`) before relying on it
being silent.

## Pocket ID clients

One client per app, created by hand in Pocket ID (a passkey is needed, so the
playbook cannot), *Generate* the secret, then repository secrets
`<APP>_OIDC_CLIENT_ID` and `<APP>_OIDC_CLIENT_SECRET`. The shared variable
`APPS_ADMIN_EMAIL` is the email of your Pocket ID user.

| app | callback URL | notes |
|---|---|---|
| tandoor | `https://tandoor.lab.<zone>/accounts/oidc/pocketid/login/callback/` | provider id is `pocketid` |
| airtrail | `https://airtrail.lab.<zone>/login` | per AirTrail's docs and Pocket ID's guide; see below |
| linkace | `https://linkace.lab.<zone>/auth/sso/oidc/callback` | |
| sure | `https://sure.lab.<zone>/auth/openid_connect/callback` | |

Then workflow **05**, environment `edge`, playbook `services`, then `ingress` on
`lab`. Without a client an app keeps only its password login: that is how a
first deploy proves it.

## First administrators

| app | account that exists from the start | after the first Pocket ID sign-in |
|---|---|---|
| tandoor | `admin`, password `DJANGO_SUPERUSER_PASSWORD` in `/etc/autolab/tandoor.env` | signing in with the same email attaches to it |
| airtrail | none: the **first account created is the owner** | sign in once, then `docker exec services-airtrail-1 airtrail-admin grant-admin <user>` if you are not the owner |
| linkace | `admin`, password `LINKACE_ADMIN_PASSWORD` in `/etc/autolab/linkace.env` | SSO users are created on first sign-in as ordinary users; promote in its UI |
| sure | none: the first user becomes super admin on a new install | sign in once; then Settings → Self-Hosting → Onboarding → Closed |

Read a break-glass password with `ssh megamp15@nebula sudo grep <KEY> /etc/autolab/<app>.env`.

When a Pocket ID sign-in works for an app, set
`autolab_services_<app>_password_login: false` in the role defaults, in a pull
request, to remove the password form (for Sure that sets
`AUTH_LOCAL_LOGIN_ENABLED=false`).

## What the playbook checks, and what it cannot

| app | proof after deploy |
|---|---|
| tandoor | its provider list (`/_allauth/browser/v1/config`) contains Pocket ID |
| linkace | `/auth/sso/oidc/redirect` answers 302 to Pocket ID's authorize URL |
| sure | its sign-in page carries the *Sign in with Pocket ID* button |
| airtrail | only that it answers: its login is drawn in the browser and offers no URL to test. Sign in once and read the callback error if Pocket ID rejects it |

AirTrail's callback is the one thing I could not verify by running it: the docs
and Pocket ID's guide say `/login`, while its code also has `/api/oauth/callback`.
If Pocket ID reports a redirect mismatch, add the other as a second callback.

## Changing an app

Each runs the project's own image at a pinned version. To ship a change, fork it
(`apps/<name>` in [Forgejo](forgejo.md)) and set `autolab_services_sources.<name>`
to `mode: fork`. That mechanism is built and proven for AdventureLog; the other
four need a `sources` entry and a `build:` stanza in their service template in the
same shape, added when the first change is made.
