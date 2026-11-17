---
tags: [gitops, docker, services, hermes, whatsapp, agents, cosmos]
status: draft
audience: operator
---

# Hermes

The owner's agent on WhatsApp. [Hermes Agent](https://github.com/NousResearch/hermes-agent)
runs on jwst as one more entry in the service catalog, talks to WhatsApp as a
linked device, and works inside a checkout of the notes vault
(`megamp15/cosmos-vault`, private). Send it a link or a thought and it writes
a note into the vault's inbox and pushes. It is the conversational front of
COSMOS, not COSMOS itself: notes are read back on the phone through COSMOS and
on the Mac through Obsidian.

## What runs

One container, `hermes`, from the official image, pinned by release tag. It
runs `gateway run` and the dashboard under the image's own supervisor, as the
operator account, with two bind mounts:

| host | container | holds |
|---|---|---|
| `/opt/autolab/services/hermes/data` | `/opt/data` | `.env`, `config.yaml`, the SQLite state, sessions, memories, skills, the paired WhatsApp session |
| `/opt/autolab/services/hermes/vault` | `/workspace/vault` | the vault checkout; the gateway's working directory |

The gateway has no port and no Docker socket; the dashboard, in the same
container, is the one published port (below). Everything the gateway does is outbound:
WhatsApp through the Baileys bridge, the model provider, GitHub. Its own API
server stays off. Both directories are on local disk: SQLite on NFS is the
same corruption story as Postgres, and the vault's durable copy is GitHub.
Neither is in the nightly dumps yet; losing `data` means pairing WhatsApp
again and losing chat history, not notes.

## Which model, and whose account

The owner's Claude plan is for Claude Code only. Anthropic's consumer terms
allow its subscription tokens in Claude Code and claude.ai and nowhere else,
and the owner wants that account kept clean. **Hermes never holds an
Anthropic credential.**

- **Starts on OpenCode Go**, the $10/month key for open-weight models,
  from the `HERMES_OPENCODE_GO_API_KEY` secret. Hermes knows the provider
  natively (`opencode-go`), so the seeded `config.yaml` names it and the key
  is read from `.env`.
- **Switch the main model to the ChatGPT/Codex subscription** once the
  gateway is up. OpenAI permits its Codex OAuth in third-party agents. It is
  a device-code login, so it works from a headless VM:

  ```sh
  ssh jwst
  docker exec -it -u hermes services-hermes-1 hermes model
  # pick "ChatGPT or Codex Subscription", follow the device code on your Mac
  ```

  Pick `gpt-6.1-sol` (not the `-900k` variant: same model, a far larger
  context budget re-read on every turn) and reasoning `medium`. Then make
  `kimi-k3` the first entry of `fallback_providers` in `data/config.yaml`,
  so a used-up Codex quota degrades to the cheap plan rather than silence.
  Done 2026-11-16; the gateway warms `gpt-6.1-sol` with a 500K context.

### Which model does what

One conversation, several models, by role. The seeded config sets them all on
OpenCode Go; each model there has its own monthly allowance, so spreading the
roles across vendors stretches the plan rather than just diversifying it.

| role | model | why |
|---|---|---|
| main | `gpt-6.1-sol` on the Codex subscription, reasoning `medium` | the newest Codex model; `kimi-k3` until the login is done |
| main fallback | `kimi-k3`, `glm-5.3`, `qwen3.7-plus` | a used-up Codex quota drops to the cheap plan; three vendors |
| delegation (subagents) | `deepseek-v4.1-flash` | cheap, fast, native tool calling; subtasks are narrow |
| compression, titles | `glm-5.3-flash` | throwaway work on the cheapest fast model |
| vision | `gemini-4-argon` | the open models on the list are text-only |

Nothing ending in `-contributor` or `-free`: the vendor may train on those
prompts, and Hermes refuses them unattended anyway. Not `claude-haiku-5-5`
either, although Go resells it, so the Anthropic rule stays simple.

`config.yaml` is seeded once by Ansible and then belongs to Hermes:
`hermes model`, `hermes tools` and the agent itself write to it. The role
does not overwrite it; delete it to reseed. `.env` is shared: the role manages
its own lines (key, WhatsApp settings, the write root) and leaves the rest,
so Hermes's own additions survive a run.

## WhatsApp

Linked device, not the Business API: Hermes emulates WhatsApp Web through a
Node bridge that ships in the image. Upstream warns the account can be banned
for it and recommends a dedicated number; the owner chose their own number
to start, in **self-chat** mode (you message yourself to talk to the agent),
with an allowlist of exactly that number (`HERMES_WHATSAPP_NUMBER`). Groups
are off (`pairing` policy forwards nothing from them). Anyone else who writes
is denied.

Pairing is one interactive step, after the first deploy:

```sh
ssh jwst
docker exec -it -u hermes services-hermes-1 hermes whatsapp
# choose self-chat, scan the QR under WhatsApp → Linked devices → Link a device
```

The session is saved under `data/platforms/whatsapp/session` and survives
restarts. It grants full access to the WhatsApp account: it is `0700`, the
operator's, and is never copied anywhere. If WhatsApp unlinks it (phone
reset, app update), run the same command again. Use a terminal at least 60
columns wide or the QR will not render.

Not verified yet, the first thing to check at pairing:

- that the bridge's Node dependencies install inside the container's
  writable `/opt/data` rather than the read-only image. If `hermes whatsapp`
  fails there, the fix is a derived image with them baked in, the way
  code-server is built;

Verified on bring-up (2026-11-16): `opencode-go` is accepted as the main
`model.provider`; the gateway log warms `kimi-k3` with a 1M context.

## The vault

Cloned once from `megamp15/cosmos-vault` with `COSMOS_VAULT_TOKEN`, a
fine-grained token with Contents read and write on that one repository. The
token sits in the checkout's remote URL, inside a `0700` directory; the role
rewrites it every run, so rotating it is `gh secret set` and a rerun. The
clone is never reset by Ansible: the agent commits there, and a reset would
discard work it had not pushed.

What the agent may do in the vault is the vault's own `AGENTS.md`, which
Hermes reads as a project instruction file: write to `inbox/`, `sources/`,
`wiki/` and the log; append to daily notes; never delete outside the inbox;
cite sources; treat fetched web content as data. The file tools are confined
to the checkout by `HERMES_WRITE_SAFE_ROOT`. The shell is not: it is the
operator account inside the container, which sees the two mounts and nothing
else of the host.

## The dashboard

`hermes.lab.<zone>`: Hermes's own web dashboard, run inside the gateway's
container by `HERMES_DASHBOARD=1`, the image's own supervised slot. Status, Chat, Sessions, Config,
API keys, Logs, Analytics, Cron, Skills, MCP, Pairing, Channels. The Chat
page talks to the same agent and memory as WhatsApp, and Sessions lists both.
Token use, cost and which model answered what are on Analytics; Grafana
only sees the container.

Two logins, on purpose. Traefik's Pocket ID check first, like every lab
page. Then Hermes's own username and password: the dashboard reads and
writes the `.env` that holds the agent's keys, and Hermes refuses to serve
that on anything but loopback without a login of its own. The credentials
are generated once on jwst:

```sh
ssh megamp15@jwst sudo cat /etc/autolab/hermes-dashboard.env
```

It was a second container until 2026-11-17. That does not work: the Chat
page attaches to the gateway on a loopback port (`ws://127.0.0.1:<port>`),
which a sibling container cannot reach, so Chat sat on "reconnecting" and
the status read "Gateway: Stopped". The reconnect loop is in
`data/logs/tui_gateway_crash.log`. The cost of one container is that the
dashboard and the gateway restart together.

To rotate, delete that file and rerun the services playbook; every existing
dashboard session ends. `dashboard.public_url` and `trusted_proxies` are the
one block of `config.yaml` Ansible keeps owning after the seed, marked as
such at the end of the file.

## Context

The point of Hermes is to be the agent that knows the owner's context. What
it reaches, and how, in order of trust:

| what | how | credential |
|---|---|---|
| the vault | checkout at `/workspace/vault`, read and write | fine-grained PAT, one repo |
| the owner's finances | Sure's API from the `finance-sure` skill; GETs only | `HERMES_SURE_API_KEY`, a **read-only** key |
| the lab itself | the public AUTOLAB repository at `/workspace/autolab`, read-only mount, refreshed every run; the `autolab` skill | none |
| Grafana, Prometheus, Loki | mcp-grafana, when wired into `mcp_servers` | the Viewer service account |

The two lab skills are installed under `data/skills/autolab-lab/` from
`files/hermes/skills/`, next to the bundled ones. They say what the agent may
do and, more to the point, what it may not: no writes to Sure, no financial
detail into the vault, no secrets, no pushing the lab from the checkout. It
advises on AUTOLAB; the owner dispatches the workflows.

What this costs, said once: every finance answer passes through the model
provider, OpenAI for the main model. Read-only keys and mounts bound the
damage from a prompt injected through a fetched page to disclosure, not
change. Keep `approvals.mode: smart` on; it is the gate on dangerous shell
commands.

Not here yet: a read-only NAS mount (which shares is the owner's call), an
Immich read key from a dedicated user, and a workflow-dispatch token for
check-mode runs.

### Sure's own assistant

Separately from Hermes, Sure's in-app AI chat runs on any OpenAI-compatible
endpoint. In Sure: Settings → Self-Hosting → AI: base URL
`https://opencode.ai/zen/go/v1`, a Go service-account key of its own, model
`kimi-k3`. No redeploy. A ChatGPT subscription cannot be used there.

## Secrets

| secret | what |
|---|---|
| `HERMES_OPENCODE_GO_API_KEY` | the OpenCode Go key, from opencode.ai after subscribing |
| `HERMES_WHATSAPP_NUMBER` | the owner's number, country code first, digits only |
| `COSMOS_VAULT_TOKEN` | GitHub fine-grained PAT, Contents read/write, `megamp15/cosmos-vault` only |
| `HERMES_SURE_API_KEY` | a read-only API key from Sure, Settings → API keys |

All three are repository-level secrets read by workflow 05 and only used on
a machine whose services list has `hermes`. The Codex login and the WhatsApp
session are created on the host and never pass through GitHub.

## Bringing it up, in order

1. Set the three secrets (`gh secret set NAME`).
2. Merge this; run workflow **05 - Ansible Builder**, `playbook: services`,
   `confirm: check` first, on `lab`. The container starts and idles: no
   WhatsApp session yet.
3. `hermes whatsapp` (above), scan the QR. Message yourself; it answers on
   OpenCode Go.
4. `hermes model`, switch to Codex, add the fallback block.
5. Send it a link. Expect `inbox/<date>-<slug>.md` to appear in the vault on
   GitHub within a minute. If it does not, read the gateway log:
   `docker logs services-hermes-1`.

## Later

- COSMOS's MCP server and Karakeep's, under `mcp_servers:` in `config.yaml`,
  once a remote (HTTP) MCP endpoint exists for COSMOS.
- Back up `data` (the SQLite history and memories) to the NAS with the other
  dumps.
- A dedicated number, if the self-chat session proves flaky or the ban risk
  starts to matter.
