---
name: inspect-host
description: Look at a running AUTOLAB machine without changing it - containers, logs, units, disk, what is listening. Use to diagnose, to confirm a deploy, or to read a value a run needs.
---

# Looking at a host

Look, do not fix. Anything changed by hand on a host is undone or orphaned
by the next run; a fix is a pull request and a run.

## Getting in

`ssh megamp15@<name>` over the lab tailnet, with `sudo` for anything
root-owned. `gitops` is CI's account and `root` is refused. If the name does
not resolve or the connection hangs on a login prompt, this machine is on
another Tailscale profile: stop and tell the user. Tenant VMs are on the
tenant's tailnet and are not reachable this way.

## Where things are

| on | what | where |
|---|---|---|
| jwst | container services | `/opt/autolab/services` (project `services`, containers `services-<name>-1`), unit `autolab-services` |
| jwst | Prometheus, Loki, Grafana, home | `/opt/autolab/observability`, unit `autolab-observability` |
| horizon | cloudflared, Traefik, Pocket ID | `/opt/autolab/ingress`, unit `autolab-ingress` |
| nebula | the apps | `/opt/autolab/services`; files on the NAS at `/mnt/apps` |
| any host | secrets and generated state | `/etc/autolab/` (root-only: read a key's name, never print a value) |
| any host | the agent | unit `alloy` |

## The usual questions

| question | command |
|---|---|
| what is running, and healthy | `sudo docker ps --format '{{.Names}}\t{{.Status}}'` |
| why a container keeps restarting | `sudo docker logs --tail 100 services-<name>-1` |
| what Compose would run | `sudo docker compose --project-directory /opt/autolab/services config --services` |
| a unit's state and last lines | `systemctl status <unit> --no-pager`, `journalctl -u <unit> -n 100 --no-pager` |
| what fires and when | `systemctl list-timers --all --no-pager` |
| what is listening, on which address | `sudo ss -ltnp` |
| what the firewall allows | `sudo ufw status` |
| disk and memory | `df -h /`, `free -m` |
| is a NAS share mounted | `findmnt /mnt/autolab` |

Logs and metrics across hosts are quicker from Grafana (Loki, Prometheus)
than from one host at a time; with `mcp-grafana` available, use it.

## Guardrails

- Read-only commands. A restart, an edit or a `compose up` by hand is the
  user's explicit call, and is followed by the pull request that makes it
  true in git.
- Never `cat` a file under `/etc/autolab/` into the conversation.
