---
tags: [gitops, docker, portainer, registry, diun, code-server, services]
status: draft
audience: operator
---

# Container services

The tooling the lab runs for itself: a UI to operate containers, a registry
to hold the images CI builds, and something to say when a pinned image has a
newer tag. Not the applications the lab exists to run — those are a tenant's
business — and not monitoring, which is [observability](./observability.md).

## Choosing what runs

One list in the machines map decides it:

```hcl
builder = {
  docker_enabled = true
  services       = ["portainer", "registry", "registry-ui", "diun", "code-server"]
}
```

The role knows five services today and refuses a name it does not know,
by name, rather than failing halfway through rendering. Each is its own
template in `roles/container-services/templates/services.d/`, assembled into
one Compose project on the host. Removing a name removes its container on
the next run (`remove_orphans`), and moving the whole set to another machine
is that line in another machine's map.

Pinned versions, like every image in this lab. Diun reports a newer tag; the
bump is a pull request.

| service | what it is for | port on the tailnet |
|---|---|---|
| `portainer` | operating containers — restart, exec, inspect, volumes, images | 9000 |
| `registry` | images built in CI, pushed and pulled inside the lab | 5000 |
| `registry-ui` | seeing what is in the registry without curl | 8082 |
| `diun` | a notification when a pinned image has a newer tag. Never updates anything | — |
| `code-server` | browser-based VS Code for the operator workspace | 8443 |

## Where they are reachable

Ports bind to the host's tailnet address, nothing else. Docker writes its own
iptables rules ahead of ufw's, so binding `0.0.0.0` would reach the LAN
whatever the host firewall says — the same reason the observability stack
binds this way.

The tailnet is the boundary, exactly as it is for Prometheus and Loki:
reaching these ports at all means being on the tailnet and passing its ACL.
Tenants are on another tailnet and cannot see them. Names under
`*.lab.<zone>` with the passkey login in front are routed automatically;
code-server is available at `code-server.lab.<zone>` when its service is enabled.

**Portainer holds the Docker socket**, which is the whole point and the whole
risk: it can do anything the daemon can. It is for operating what these roles
define, not for defining it. A stack deployed from Portainer's UI exists
nowhere in git and will be overwritten or orphaned by the next Ansible run.

**The registry has no authentication**, on purpose and for now: the tailnet is
the gate, and `docker login` is not a browser, so it cannot use the passkey
login that fronts everything else. Pushing from CI, or letting a tenant pull
over the management bridge, both need an htpasswd credential first — neither
is true yet.

## Names and the login

Each service with a UI gets `<name>.lab.<zone>`, a real certificate, and the
same passkey session as everything else — Traefik's OIDC middleware, from the
catalog's `login: plugin`. Turning a service on in the machines map is
therefore enough: the route appears with it.

Two exceptions, both honest:

- **Portainer keeps its own login too.** OIDC is a paid feature in Portainer;
  Community Edition has only local accounts. So it is one passkey at the
  edge and then Portainer's admin password behind it. That password is a
  repository secret written to a file the container reads at first start, so
  Portainer never opens its setup page — which expires five minutes after the
  container starts and then refuses to create an admin until it is restarted.
- **The registry answers `docker`, not a browser.** `docker login` and
  `docker push` cannot complete a passkey challenge, so `registry.lab.<zone>`
  skips the middleware. The name still earns its keep: Docker refuses a
  plain-HTTP registry unless every client carries an `insecure-registries`
  entry, and this one has a real certificate. The tailnet is the gate, as it
  is for Prometheus.

The port and the login mode live once, in `playbooks/group_vars/all.yml`,
because two roles on two different machines have to agree on them: the
services host publishes the port, and the ingress host routes to it.

**code-server is intentionally different from Portainer.** It is reached at
`code-server.lab.<zone>` through the tailnet-only Traefik listener and Pocket ID
middleware; it binds only jwst's tailnet address on port 8443. Its workspace is
`/opt/autolab/services/code-server/workspace`, owned by `megamp15`, and the
sibling `config`, `data` and `cache` directories hold its settings, its
extensions and the rest of its state. All four are mounted, because the image's
own `/home/coder` belongs to uid 1000 and an unmounted path is both unwritable
and lost on the next image bump. The container runs with megamp15's UID/GID so
files remain normal operator files. It uses `--auth none` because Pocket ID and
the tailnet are the authentication boundary; it does not expose a public
hostname. It deliberately has no Docker socket and no broad `/home` mount:
browser editing should not grant daemon control or expose the operator's home
directory.

## Diun

It watches every running container on the host and compares the image's tag
against its registry, on a schedule, and publishes to the same ntfy topic as
the alerts. It never pulls and never restarts anything: versions are pinned
in git, and an image that changed underneath you is the thing this lab is
built to avoid. The notification is the input to a pull request.
