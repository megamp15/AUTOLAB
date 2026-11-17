---
name: alert
description: Respond when an AUTOLAB alert fires or something is down - a page on the phone, a red row on home, a service that will not open. Use to find the cause, and to decide what is a fix and what is a rerun.
---

# Something is wrong

Rules, thresholds and delivery: `docs/gitops/observability.md`, "Alerting".
Schedules and repeat intervals: `docs/gitops/operations.md`.

## Steps

1. Read the alert or the symptom exactly: which rule, which host, since when.
2. Look before touching: home's row, the rule's query in Grafana, then
   `inspect-host`. Recent change first: `git log --oneline -10` and the last
   runs (`gh run list --limit 10`); most breakage follows a deploy.
3. Find the row below, or reason from what step 2 showed.
4. Say what you found and what you propose, in two lines, before changing
   anything. A rerun of the playbook that owns the thing is the usual fix; a
   repeated cause is a pull request.
5. Done when the alert has cleared by itself and home is green. Then
   `prove` if the fix changed what the alert watches.

## First look, by alert

| alert | usually | look at |
|---|---|---|
| Guest is stopped but set to start on boot | a node reboot it did not come back from, or out of memory on the node | the node's task log; the node's free memory |
| Agent is not reporting | `alloy` stopped, the host is down, or a new machine never had `05` `observability` | `systemctl status alloy`; `observe` |
| Backup is missing | last night's job failed for that guest | `backup-restore`, "A backup failed" |
| Backup collector is stale | the collector's timer on jwst, not the backups | `systemctl list-timers` on jwst |
| Tunnel is down | cloudflared on horizon, or horizon itself; every public name answers Cloudflare's 530 | `docker ps` on horizon; `journalctl -u autolab-ingress` |
| Container is restart-looping | a bad config or a missing secret after a deploy | `docker logs` for that container |
| Container has vanished | a service removed from the map, or a failed recreate | the last `05` `services` run |
| Root filesystem almost full | images and build cache, or logs | `docker system df`, `du -xh / --max-depth=2` |
| Memory nearly exhausted | jwst under a code-server build | `docker stats --no-stream` |
| Proxmox storage almost full | old restore tests, templates, or a growing guest | `pvesm status` on the node |
| An app database has no recent dump / does not restore | nebula's dump timer or the NAS mount | `docs/gitops/nebula.md` |

## Not an alert, but down

| symptom | usually |
|---|---|
| every `*.lab` name fails, public names work | split DNS, or dnsmasq on horizon waiting for the tailnet after a boot |
| a `*.lab` name gives 404 | no route: the service is not in the map, or `05` `ingress` has not run since it was added |
| a name gives 502 | the route is there and the app is not: the container, or its host |
| a sign-in is refused | `pocket-id`, "When a login is refused" |
| nothing on a node answers | the node; its guests come back by themselves when it does |
| a rerun fails for every host | one machine without `gitops`: `run-workflow`, "When a run fails" |

## Guardrails

- Silencing an alert or raising its threshold is not a fix.
- A restart by hand is the user's call, and the cause still gets found.
