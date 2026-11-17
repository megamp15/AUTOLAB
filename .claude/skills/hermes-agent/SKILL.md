---
name: hermes-agent
description: Change what Hermes (the owner's WhatsApp agent on jwst) knows, reaches or runs on - its skills, a new source, a credential, its model. Use to give Hermes a capability or take one away, or when it stops answering.
---

# Hermes

Hermes reads and explains; it does not deploy. What runs, which model, what
it may reach and why: `docs/gitops/hermes.md`.

## What it reaches today

The vault (read and write), Sure (a read-only key), this repository (a
read-only checkout), and Grafana when wired. Each has its own credential
with the least it needs.

## Giving it a capability

1. Decide the least it needs: read-only wherever a read-only key or mount
   exists. A write capability is the user's explicit decision.
2. Its instructions: a skill under
   `roles/container-services/files/hermes/skills/<name>/`, saying what it
   may do and, as plainly, what it may not. The run installs them under
   `data/skills/autolab-lab/`.
3. Its credential: `secret`. Passed to the container's environment by the
   role, never written into a skill.
4. Its config: only the keys this repository owns. `config.yaml` is also
   written by Hermes itself; the role must not own a block Hermes writes
   into.
5. `docs/gitops/hermes.md` (the "Context" table), home's AI tab (`aiCard`
   and `AI_EDGES` in the page: `surfaces`).
6. `pull-request`, then `run-workflow`: `05`, `lab`, `services`,
   `limit=jwst`.
7. Done when a message asking for the new thing gets a right answer, and a
   message asking it to go past its limit is refused.

## When it stops answering

| symptom | look at |
|---|---|
| no reply on WhatsApp | `docker logs services-hermes-1`; the WhatsApp session may need pairing again, by hand: the doc's "WhatsApp" |
| replies, but cannot read something | that credential expired, or the mount is missing |
| the dashboard opens but Chat does not connect | the dashboard must run in the gateway's container |

## Guardrails

- No workflow-dispatch token, no Docker socket, no write key to finances.
- Everything Hermes reads passes through its model provider. A new source
  is also a disclosure decision: say so to the user.
