---
tags: [gitops, rustdesk, remote-desktop, tailnet, services]
status: draft
audience: operator
---

# RustDesk: remote desktop between your own machines

The self-hosted RustDesk server (`hbbs` and `hbbr`, AGPL, no device limit, no
licence) on jwst. It is for the lab's own machines and your personal ones. It is
not for a business's customers: that is a separate server, on a public VPS, and
nothing here is shared with it.

```
your Mac ── RustDesk client ──┐                       ┌── lab PC / laptop / phone
                              │   tailnet only        │   RustDesk client
                              ▼                       ▼
                         jwst :21115-21117 (hbbs introduces, hbbr relays)
```

Enabled by `"rustdesk"` in jwst's `builder.services`. It binds the tailnet
address only, so a machine that is not on the tailnet cannot reach it at all.
There is no name under `*.lab.<zone>` and no login page: RustDesk speaks raw
TCP and UDP, which Traefik cannot carry, so it is outside the ingress.

| port | what | |
|---|---|---|
| 21115 | TCP, NAT test | hbbs |
| 21116 | TCP and UDP, ID registration and hole-punching | hbbs |
| 21117 | TCP, relay | hbbr |

The web-client ports (21118, 21119) are not published.

## The key

On first start `hbbs` makes a keypair in `/opt/autolab/services/rustdesk/`
(root-only, with the peer database beside it). Both containers run with `-k _`,
which refuses any client that does not present the public half. The deploy
prints it, and you can read it any time:

```bash
ssh megamp15@jwst sudo cat /opt/autolab/services/rustdesk/id_ed25519.pub
```

It is public by design. The private half and the database are in the VM's
backups; **losing the directory means re-pointing every enrolled machine**, so
it is the thing to keep when rebuilding jwst.

## Deploying

Merging does not deploy it. Run the `services` playbook against the lab stack
from workflow 05 (check mode first, as for everything on a host). The run ends
by waiting for the public key to exist, which proves hbbs started and wrote it.

## Enrolling a machine

Install the client from rustdesk.com, then **Settings, Network, ID/Relay server**:

| field | value |
|---|---|
| ID server | `jwst.<tailnet>.ts.net` |
| Relay server | leave empty (hbbs hands out its own) |
| API server | leave empty |
| Key | the public key above |

The machine must be on the tailnet. On the Mac with two Tailscale profiles it
has to be the lab profile.

For a machine you want to reach while nobody is sitting at it, set a permanent
password in the client (**Settings, Security**) and keep it in a password
manager. The free server has no central vault for them.

## Proving it, by breaking it

Reading the config is not evidence that the key is enforced. After the first
two machines are enrolled and can connect:

1. Put a wrong character in a client's Key field. It must report that it cannot
   connect, not connect anyway. That is `-k _` working.
2. From a machine off the tailnet (phone on cellular, Tailscale off), try the ID
   server. It must not connect at all.
3. `docker compose up -d --force-recreate` in `/opt/autolab/services` and read the
   key again. It must be the same (it was, in the local test before this was
   merged).

## Things that will mislead you

- **The image is `scratch`: no shell, no `cat`.** `docker exec ... cat` fails.
  That is why the key lives in a host directory the role reads directly.
- **hbbs drops a relay name it cannot resolve, silently.** `-r some.name:21117`
  with a name the container cannot resolve logs `relay-servers=[]` and carries on;
  with an address it logs `relay-servers=["<addr>:21117"]` and never tests it.
  The role passes the tailnet address for this reason, not the MagicDNS name.
- **Clients only need the ID server.** They learn the relay from it. A relay
  address typed into a client is a second place to be wrong.
- **Docker bypasses ufw.** The ports bind the tailnet address, never `0.0.0.0`,
  for the same reason as every other service here.

## Moving it to a VPS later

Nothing about the service is jwst-specific. The same `rustdesk` entry on a VPS
machine (the VPS track) runs it with public ports, after which two things change:
the ports must be open to the internet, and `-k _` stops being an extra and
becomes the only thing between the internet and the relay. Copy the key directory
across and every enrolled client keeps working with only the ID server edited.
