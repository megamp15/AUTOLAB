---
tags: [gitops, docker, portainer, registry, diun, services]
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
  services       = ["portainer", "registry", "registry-ui", "diun"]
}
```

The role knows four services today and refuses a name it does not know,
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

## Where they are reachable

Ports bind to the host's tailnet address, nothing else. Docker writes its own
iptables rules ahead of ufw's, so binding `0.0.0.0` would reach the LAN
whatever the host firewall says — the same reason the observability stack
binds this way.

The tailnet is the boundary, exactly as it is for Prometheus and Loki:
reaching these ports at all means being on the tailnet and passing its ACL.
Tenants are on another tailnet and cannot see them. Names under
`*.lab.<zone>` with the passkey login in front follow in their own change.

**Portainer holds the Docker socket**, which is the whole point and the whole
risk: it can do anything the daemon can. It is for operating what these roles
define, not for defining it. A stack deployed from Portainer's UI exists
nowhere in git and will be overwritten or orphaned by the next Ansible run.

**The registry has no authentication**, on purpose and for now: the tailnet is
the gate, and `docker login` is not a browser, so it cannot use the passkey
login that fronts everything else. Pushing from CI, or letting a tenant pull
over the management bridge, both need an htpasswd credential first — neither
is true yet.

## Diun

It watches every running container on the host and compares the image's tag
against its registry, on a schedule, and publishes to the same ntfy topic as
the alerts. It never pulls and never restarts anything: versions are pinned
in git, and an image that changed underneath you is the thing this lab is
built to avoid. The notification is the input to a pull request.
