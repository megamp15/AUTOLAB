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
runs `gateway run` under the image's own supervisor, as the operator account,
with two bind mounts:

| host | container | holds |
|---|---|---|
| `/opt/autolab/services/hermes/data` | `/opt/data` | `.env`, `config.yaml`, the SQLite state, sessions, memories, skills, the paired WhatsApp session |
| `/opt/autolab/services/hermes/vault` | `/workspace/vault` | the vault checkout; the gateway's working directory |

No port, no Traefik route, no Docker socket. Everything it does is outbound:
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

  Then make OpenCode Go the fallback, so a used-up Codex quota degrades to
  the cheap plan rather than silence. Edit `data/config.yaml` and add:

  ```yaml
  fallback_providers:
    - provider: opencode-go
      model: kimi-k3
  ```

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

Not verified yet, the first things to check on bring-up:

- that the bridge's Node dependencies install inside the container's
  writable `/opt/data` rather than the read-only image. If `hermes whatsapp`
  fails there, the fix is a derived image with them baked in, the way
  code-server is built;
- that `opencode-go` is accepted as the main `model.provider` in the seeded
  config (the docs list it in the provider registry and name its key
  variable; the main-model path was not exercised). If the gateway log
  rejects it, `hermes model` → Custom endpoint,
  `https://opencode.ai/zen/go/v1`, same key.

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

## Secrets

| secret | what |
|---|---|
| `HERMES_OPENCODE_GO_API_KEY` | the OpenCode Go key, from opencode.ai after subscribing |
| `HERMES_WHATSAPP_NUMBER` | the owner's number, country code first, digits only |
| `COSMOS_VAULT_TOKEN` | GitHub fine-grained PAT, Contents read/write, `megamp15/cosmos-vault` only |

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
