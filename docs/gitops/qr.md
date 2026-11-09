---
tags: [gitops, qr, cloudflare, tunnel, services]
status: active
audience: operator
---

# QR codes that redirect

A printed QR code encodes a short address, not the destination. The address
redirects to wherever you say, and you can change that later without
reprinting. The destination is usually a Google Form.

```
phone scans  →  https://go.paradigm-prints.com/signup
                       │  Cloudflare, the Paradigm Prints account's tunnel
                       ▼
                 paradigm-tunnel ──▶ qr-public:8080   302 → the Google Form
                                          │
                                   one SQLite file          ◀── qr (admin page)
                                                               qr.lab.<zone>
                                                               tailnet + passkey
```

## Two containers, one image

| container | listens | reachable from |
|---|---|---|
| `qr-public` | `GET /<name>` → 302, `GET /healthz`. Nothing else: no page, no API | the `paradigm-public` network, where the tunnel connector is |
| `qr` | the page and its API, plus the PNG and SVG of each code | jwst's tailnet address, port 8097, behind the passkey at `qr.lab.<zone>` |

The admin page has no login of its own, so it must never be somewhere a tunnel
can reach. It is on the default network only; the connector and `qr-public`
are on `paradigm-public` only. Proved on a built stack: from `paradigm-public`,
`qr:8081` does not resolve and `qr-public:8080/api/links` is 404.

Both containers run as an unprivileged user in a read-only filesystem with no
capabilities, and share `/opt/autolab/services/qr/data/qr.db` (SQLite, WAL).
The public one writes to it too, to count scans. The directory belongs to uid
10001, the account inside the image.

## The Paradigm tunnel

The Paradigm Prints domain is in a different Cloudflare account from the lab's,
so horizon's tunnel cannot serve it. `paradigm-tunnel` is a second connector
on jwst with that account's own tunnel token. It is not specific to QR codes:
one tunnel carries any number of hostnames. To publish another service:

1. Put the service on the `paradigm-public` network in its compose template.
   **Only a container that is safe to be public goes there.**
2. In the Paradigm Prints Cloudflare dashboard: Zero Trust → Networks → Tunnels
   → the tunnel → Published application routes → add the hostname with service
   `http://<container>:<port>`. DNS is created for you.

Whoever controls that account's tunnel can point a hostname at anything on
`paradigm-public`. That is why the network holds only public things.

### First-time setup

1. In the Paradigm Prints Cloudflare account create a tunnel (Docker
   environment; do not run the command), and copy the token after `--token`.
2. Add a route: `go.paradigm-prints.com` → `http://qr-public:8080`.
3. GitHub, `lab` environment: secret `PARADIGM_TUNNEL_TOKEN` (the token) and
   variable `QR_PUBLIC_URL` (`https://go.paradigm-prints.com`).
4. Run workflow 04 apply for `lab` (the machines map gained two services), then
   05 for the services host. The role refuses to run without the variable and
   the secret, and says which.

Before step 4 the tunnel shows inactive and the hostname returns a Cloudflare
error. That is expected.

## Using it

Open `https://qr.lab.<zone>`, press **New QR code**, give it a name, the
destination and, if you like, a short address (random otherwise). The card shows
the code with PNG and SVG downloads (SVG for print shops), the scan count and
the last scan. **Edit** changes the name and destination; the short address is
fixed because it is what the code contains.

- Redirects are `302` with `Cache-Control: no-store`, so an edit takes effect
  at once and nothing caches the old destination.
- A `HEAD` request (link-preview bots, uptime probes) is not counted as a scan.
- Destinations must be `http(s)://`; `javascript:`, `data:` and the like are
  refused, as is a destination on the public host itself (a loop).
- Codes use the highest error correction (25% recoverable), for scuffed paper.
- Deleting a code stops every printed copy of it.

## Backups

State is one file, `/opt/autolab/services/qr/data/qr.db`. Losing it loses the
list of short addresses, and every printed code then returns 404. Printed codes
cannot be regenerated from the destinations, because the short names live only
here. Check that this path is in the host's backup before printing at scale.

## Changing the code

The source is `builders/ansible/roles/container-services/files/qr/`: one Go
file, one HTML page, a Dockerfile. The image is built on jwst; its tag is a
hash of those files, so any change is a new tag and the next run builds it.
The tests run with `go test` from that directory (Go 1.26).
