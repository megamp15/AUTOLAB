---
name: app-fork
description: Change the code of an upstream app AUTOLAB runs (AdventureLog, Karakeep, Sure) through its fork in Forgejo. Use for a fix or feature in an app's own source, or to take upstream's changes into a fork.
---

# Patching an app we run

The lab's git host keeps a mirror of each upstream project and our fork of
it; the fork is what gets built. How that is set up: `docs/gitops/forgejo.md`
and `docs/gitops/apps.md`.

| org in Forgejo | what | changed by |
|---|---|---|
| `mirrors/<app>` | a pull mirror of upstream, refreshed every 8 hours | nobody |
| `apps/<app>` | our fork | us |

## Steps

1. Clone `https://forgejo.lab.<zone>/apps/<app>.git` (tailnet; write access
   is a Forgejo token the user holds). Make the change and push a commit.
2. First change to an app other than AdventureLog: give it a `sources`
   entry and a `build:` stanza in its service template, in AdventureLog's
   shape. That is a change to this repository.
3. In `roles/container-services/defaults/main.yml`,
   `autolab_services_sources.<app>`: `mode: fork`, `ref:` the commit or tag.
4. `pull-request`, then `run-workflow`: `05`, `environment=edge`,
   `playbook=services`, `limit=nebula`. nebula checks the fork out at that
   ref, builds the image, tags it with the commit and recreates the
   container. Building takes minutes and a few GB of memory.
5. Done when the container runs the image tagged with that commit, and the
   change is visible in the app.

## Taking upstream's changes

A pull request in `apps/<app>` from `mirrors/<app>`, or merge locally and
push. Then step 3 with the new commit. Read upstream's release notes for a
migration first (`bump-version`).

## Going back

`mode: upstream` returns to the project's own pinned image.

## Guardrails

- A fork's history is never reset. The bootstrap creates what is missing
  and leaves what exists.
- A database migration in a patch needs a dump first:
  `docs/gitops/nebula.md`.
