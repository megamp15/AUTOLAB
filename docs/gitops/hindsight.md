---
tags: [gitops, services, ai, hindsight, memory]
status: draft
audience: operator
---

# Hindsight

One memory shared by the owner's agents. Claude Code, Codex and OpenCode on the
Mac and Hermes on jwst all write what happened in their sessions to it and recall
from it, so switching models in T3 Code keeps the context. Upstream:
[vectorize-io/hindsight](https://github.com/vectorize-io/hindsight), MIT.

```text
 Mac (T3 Code)                          jwst
 Claude Code ─┐                         ┌──────────────────────────────────┐
 Codex ───────┼── tailnet, API key ────►│ hindsight  API :8120 (/mcp)      │
 OpenCode ────┘   hindsight-api.lab     │            UI  :8119 (passkey)   │
                                        │            Postgres (pg0) in the │
 Hermes ──────── hindsight-agents ─────►│            hindsight-data volume │
                 http://hindsight:8888  └──────────────┬───────────────────┘
                                                       │ extraction only
                                                       ▼
                                          OpenCode Go (its own key)
```

## What it is for

It is one of three layers:

| Layer | Holds | Where |
|---|---|---|
| Reviewed knowledge | Hardware, services, decisions, quirks | The vault (`megamp15/cosmos-vault`) |
| Always-loaded rules | Short instructions | Global `CLAUDE.md` / `AGENTS.md`, each repo's AGENTS.md |
| Session memory | What happened, recalled when relevant | **Hindsight** |

**Banks are per project, not per agent:** `autolab`, `qnta`, `cosmos`, plus `mahir`
for preferences that hold everywhere and `hermes` for Hermes's own chats. An agent
working in a project uses that project's bank, whichever model it is.

Paradigm Prints is a separate business and gets its own stack. It never writes here.

## How it runs

- **One container**, the full image: the API on 8888, the control plane on 9999, and
  Postgres embedded (pg0) in the named volume `hindsight-data`. Embeddings and the
  reranker run locally on jwst's CPU. The first start takes minutes while they warm up.
- **Its own model** only extracts and merges facts: `glm-5.3-flash` on OpenCode Go,
  with `HINDSIGHT_OPENCODE_GO_API_KEY`, or Hermes's key until that exists. Without a key it starts
  but retains nothing. The agents keep their own models.
- **Never an Anthropic credential.** Hindsight offers a Claude Code provider; it is not
  used. The owner's Claude plan is for Claude Code only.
- **Memory:** limited to 2.5 GB. jwst had 3.6 GB free before it (2026-11-25).

## Access

| Who | How | Credential |
|---|---|---|
| The owner, in a browser | `hindsight.lab.<zone>` → control plane | Pocket ID passkey |
| Coding agents on the Mac | `hindsight-api.lab.<zone>`, or `jwst:8120` on the tailnet | API key |
| Hermes | `http://hindsight:8888` on the internal `hindsight-agents` network | API key |

The API key is generated once on jwst in `/etc/autolab/hindsight.env` (root, `0600`)
as `HINDSIGHT_API_TENANT_API_KEY`. The control plane sends the same key. Read it with:

```sh
ssh jwst 'sudo grep TENANT_API_KEY /etc/autolab/hindsight.env | cut -d= -f2'
```

No passkey on the API, for the same reason as the registry: agents cannot answer
one. The tailnet is the gate, and the key is required on every call.

## Connecting the agents

These are one-time steps after the first deploy. They are not in Ansible yet.

**Hermes** (inside its container, then a restart):

```sh
ssh jwst
sudo docker exec -it -u hermes services-hermes-1 hermes plugins install hindsight --enable
sudo docker exec -it -u hermes services-hermes-1 hermes memory setup   # pick hindsight, local_external
```

Then in `/opt/data/hindsight/config.json`: `"mode": "local_external"`,
`"api_url": "http://hindsight:8888"`, `"bank_id": "hermes"`,
`"recall_additional_banks": ["mahir"]`. Put `HINDSIGHT_API_KEY=<key>` in `data/.env`.

**Claude Code, Codex, OpenCode on the Mac:**

```sh
npx @vectorize-io/hindsight-coding-agents install claude-code   # then codex, opencode
```

Choose the self-hosted server, `https://hindsight-api.lab.<zone>` and the API key.
Each repository picks its bank in `.hindsight/config.toml`:
`bank_id = "autolab"` (or `qnta`, `cosmos`).

## Backups

The `hindsight-data` volume is on jwst's disk and in the nightly PBS backup of jwst.
There is no separate database dump yet.

## Checks

```sh
curl -fsS http://jwst.<tailnet>:8120/health
curl -fsS -H "Authorization: Bearer $KEY" http://jwst.<tailnet>:8120/v1/default/banks
```
