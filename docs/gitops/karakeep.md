---
tags: [gitops, apps, nebula, karakeep, bookmarks, pocket-id, hermes, vault]
status: draft
audience: operator
---

# Karakeep

Bookmarks that fetch themselves. Save a link and [Karakeep](https://karakeep.app)
keeps the page's text, a screenshot, a full-page archive and, for a reel or
a short, the video; a model tags and summarises it when a key is set. It
replaced LinkAce on 2026-11-17, which stored a link and nothing behind it.

It is one of [the self-hosted apps](apps.md) on [nebula](nebula.md):
`karakeep.lab.<zone>`, tailnet only, Pocket ID sign-in.

## What runs

| container | what | state |
|---|---|---|
| `karakeep` | the web app and its workers, one image, pinned by version | SQLite in the `karakeep-data` volume on nebula's disk; fetched assets on the NAS under `karakeep/assets` |
| `karakeep-chrome` | the headless browser it drives to render a page. Published only as `release`, so pinned by digest | none |
| `karakeep-meili` | search. The version Karakeep's own compose file names | an index in `karakeep-meili`, rebuilt from the database |

The database is on local disk for the reason Postgres is: SQLite on NFS
corrupts. It is in the nightly dumps with the Postgres databases: SQLite's
online backup copies it to local scratch, `integrity_check` must pass, and the
copy lands in `/mnt/apps/backups/karakeep/` on the NAS as a `.sqlite` file.
The weekly restore test opens the newest copy and compares its tables with
the live file. To restore, stop `karakeep` and copy the newest file over
`db.db` in the `karakeep-data` volume. `queue.db` beside it is the job queue
and is not kept.

Videos are kept up to `autolab_services_karakeep_video_max_mb` (200).

## Sign-in

The edge `services` run creates the Pocket ID client (callback
`/api/auth/callback/custom`), restricted to the `admins` group. Karakeep
makes the **first account created its admin**, so sign in with Pocket ID
before anything else. When that works, set
`autolab_services_karakeep_password_login: false` in a pull request: the
password form goes and the sign-in page redirects straight to Pocket ID.

The playbook proves only that `/api/health` answers. The sign-in is proven
by signing in.

## Tagging

Any OpenAI-compatible endpoint. Here: OpenCode Go, a service-account key of
Karakeep's own in the `KARAKEEP_OPENCODE_GO_API_KEY` secret, `kimi-k3` for
text and `gemini-4-argon` for images. Never an Anthropic credential.

Without the secret Karakeep saves and fetches and tags nothing. Setting it
later is `gh secret set KARAKEEP_OPENCODE_GO_API_KEY` and an edge `services`
run; in Karakeep, Admin → Background Jobs re-runs tagging for what was saved
before.

Not verified: that OpenCode Go's models accept Karakeep's request shape.
`INFERENCE_OUTPUT_SCHEMA=json` is set because structured output is an OpenAI
feature the open models may not have. If tags do not appear, read
`docker logs services-karakeep-1` on nebula.

## Where a link ends up

Two stores, on purpose. The vault holds what the owner wants to know;
Karakeep holds what the owner wants to find again.

| the link is | it goes to | what the vault keeps |
|---|---|---|
| worth reading or watching: an article, a video, a thread | a source note, `sources/<slug>.md`: summary, key points, full text or transcript, the URL | the note, linked from `wiki/index.md`, one line in `meta/log.md` |
| only a bookmark: a product, a tool, a place, a shop | Karakeep, with its page, screenshot, video and tags | one line in `meta/log.md` with the Karakeep link |

Either way the drop in `inbox/` is deleted once it is filed; the inbox is a
queue, not a store. The rule is the vault's own `AGENTS.md`, "Inbox
contract".

Not built yet, in order:

1. **Hermes saves to Karakeep.** A Karakeep API key (Settings → API Keys) in
   Hermes's `.env` and a skill. It is the first source Hermes can write to
   besides the vault; the key can add and tag bookmarks, nothing else in the
   lab.
2. **The sorter.** Today a link sent on WhatsApp lands in `inbox/` and stays
   there: nothing runs the inbox contract. The plan is headless Claude Code
   on jwst on a timer.

## Secrets

| secret | what |
|---|---|
| `KARAKEEP_OPENCODE_GO_API_KEY` | OpenCode Go service-account key, models permission only |

`NEXTAUTH_SECRET` and the search key are generated on nebula
(`autolab-gen-credentials`) into `/etc/autolab/karakeep.env` and never
leave it. The Pocket ID client secret is in root-only state there too.

## Bringing it up

A machines-map change, so in order: `03` plan and `04` apply on `edge`;
`05`, `environment: edge`, `playbook: services`, `limit: nebula`, check
then apply; `05`, `environment: lab`, `playbook: ingress` for the name;
`05`, `lab`, `services`, `limit: jwst` for the dash tile. The home card
applies on merge.
