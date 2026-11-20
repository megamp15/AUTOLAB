---
tags: [gitops, apps, nebula, pocket-id, tandoor, airtrail, karakeep, sure]
status: draft
audience: operator
---

# The self-hosted apps

Four apps on [nebula](nebula.md), beside [AdventureLog](adventurelog.md) and
[Forgejo](forgejo.md). Each is `<name>.lab.<zone>`, tailnet only, signs people in
with its own Pocket ID client and keeps its files on the NAS. The three on
Postgres have their database dumped nightly and restore-tested weekly;
[Karakeep](karakeep.md) is on SQLite and is not in the dumps yet.

| app | for | database | files on the NAS | idle RAM |
|---|---|---|---|---|
| `tandoor` 2.7.2 | recipes, meal plans, shopping lists | Postgres | `tandoor/media` | ~850 MB (its workers) |
| `airtrail` 3.14.0 | flights on a map | Postgres | `airtrail/uploads` | ~50 MB |
| `karakeep` 0.35.0 | bookmarks that fetch and tag themselves, see [karakeep](karakeep.md) | **SQLite**, local volume | `karakeep/assets` | not measured yet; limits 1 GB + 768 MB browser + 384 MB search |
| `sure` 2026.11.14-alpha | accounts, budgets, net worth | Postgres | `sure/storage` | web and worker ~375 MB each |

Karakeep took LinkAce's place on 2026-11-17. LinkAce's containers are gone;
its MariaDB volume (`services_linkace-db`) and `/etc/autolab/linkace*.env`
were left on nebula, and its Pocket ID client was left in Pocket ID. Remove
them by hand once nothing in it is wanted.

**Sure holds financial data.** It is the one app whose sign-in page you should
not hand out. No bank aggregator or AI provider is configured: those are
credentials entered in its settings, and nothing here enters them. Sure's docs
mention product analytics that is on by default; I could not confirm the switch
that turns it off, so check its release notes (`POSTHOG_*`) before relying on it
being silent.

### Sure upgrade (0.7.6-hotfix.1 to 2026.11.14-alpha)

Rehearsed on a scratch Sure built like this one (same pinned Postgres and
Redis, 768 MB limits, explicit `ACTIVE_RECORD_ENCRYPTION_*` keys), loaded with
four loans and 96 balances on 0.7.6-hotfix.1, then switched to the new image
over the same volumes. Up in 14 s, all 487 migrations applied, balances
unchanged, about 380 MB per container.

Sure's upgrade notes say to keep `SECRET_KEY_BASE` and the encryption keys.
`sure.env` is generated once (`autolab-gen-credentials`) and kept, so an image bump leaves them alone.

The new image logs a `[SECURITY]` warning until its encryption backfill has
run once. It is not an outage. Run it after the deploy, dry run first, and only
write if the dry run ends in `"failed_count":0`:

```bash
docker exec services-sure-1 bin/rails "security:backfill_encryption[100,1]"   # dry run
docker exec services-sure-1 bin/rails "security:backfill_encryption[100,0]"   # writes
docker restart services-sure-1 services-sure-worker-1
```

Take the dump first (`systemctl start autolab-db-backup`). Migrations do not
reverse, so going back to 0.7.6-hotfix.1 means restoring that dump.

## Pocket ID clients

The edge `services` playbook creates a client for each app with the callback
URLs below, restricts sign-in to Pocket ID's `admins` group, and configures the
apps. Generated client credentials are stored in root-only state on nebula;
see [AdventureLog](adventurelog.md#setting-it-up) for recovery and backup notes.
Local password login remains available until SSO is verified.

| app | callback URL |
|---|---|
| tandoor | `https://tandoor.lab.<zone>/accounts/oidc/pocketid/login/callback/` |
| airtrail | `https://airtrail.lab.<zone>/login` |
| karakeep | `https://karakeep.lab.<zone>/api/auth/callback/custom` |
| sure | `https://sure.lab.<zone>/auth/openid_connect/callback` |

## First administrators

| app | account that exists from the start | after the first Pocket ID sign-in |
|---|---|---|
| tandoor | `admin`, password `DJANGO_SUPERUSER_PASSWORD` in `/etc/autolab/tandoor.env` | attaches by email only if Pocket ID reports the email verified; otherwise link it by hand |
| airtrail | none: the **first account created is the owner** | sign in once, then `docker exec services-airtrail-1 airtrail-admin grant-admin <user>` if you are not the owner |
| karakeep | none: the **first account created is the admin** | sign in with Pocket ID first, before anyone uses the password form |
| sure | none: the first user becomes super admin on a new install | sign in once; then Settings → Self-Hosting → Onboarding → Closed |

On a new AirTrail install, `/login` first shows the owner-account setup form.
Create that first local owner account there. Once setup finishes, sign in with
Pocket ID from AirTrail's normal login page.

Read a break-glass password with `ssh megamp15@nebula sudo grep <KEY> /etc/autolab/<app>.env`.

When a Pocket ID sign-in works for an app, set
`autolab_services_<app>_password_login: false` in the role defaults, in a pull
request, to remove the password form (for Sure that sets
`AUTH_LOCAL_LOGIN_ENABLED=false`).

## Verified emails

Several apps trust an email only if the identity provider says it is verified:
AdventureLog and Tandoor attach a first Pocket ID sign-in to an existing account
by email only then, and LinkAce (`SSO_REQUIRE_VERIFIED_EMAIL=true`) and Sure
refuse a sign-in whose email is not. **Pocket ID reports emails as unverified
unless told otherwise.** Without that, a first sign-in to LinkAce or Sure is
refused, and one to AdventureLog or Tandoor lands on a sign-up form instead of
your account.

### The setting

Pocket ID → **Application Configuration** → **Email** tab → **General** →
**Emails verified by default**. Its own description: *when enabled, users' email
addresses will be marked as verified by default upon signup or when their email
address is changed.* It is instance-wide and off by default. (The tab row is
General · User Creation · Passkeys · Email · LDAP · OIDC; the switch sits under
*Require Email Address*, above the SMTP fields. SMTP is not needed for it.)

Turning it on is reasonable here: sign-up is closed and every email is one an
admin entered. It is a statement that Pocket ID's users own their emails, so
re-think it before ever opening sign-up.

**It applies at signup or when an email changes, not retroactively.** A user who
already existed keeps `emailVerified = false` until their email is re-saved:
Administration → Users → the user → set the email (change it, save, change it
back if the form refuses an unchanged value) and save. As code, the same switch
is `EMAILS_VERIFIED=true` on the Pocket ID container (it then becomes read-only in
the UI); it has the same signup-or-change behavior.

### Proving it worked

Sign in to **LinkAce** or **Sure** with Pocket ID: they refuse an unverified
email, so a successful first sign-in is the proof, and a refusal means this
user's flag did not change. Sure has been confirmed working this way.

### The alternative

Leave the policy strict and link one account by hand (what was done for
AdventureLog: tie that Pocket ID user's subject id to the existing local user).
That trusts one identity instead of every email.

## What the playbook checks, and what it cannot

| app | proof after deploy |
|---|---|
| tandoor | its provider list (`/_allauth/browser/v1/config`) contains Pocket ID |
| karakeep | only that `/api/health` answers. Sign in once to prove Pocket ID |
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
