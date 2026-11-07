---
tags: [operations, schedules, notifications, architecture, security]
status: alpha
audience: operator
---

# Lab operations

The homepage has three views: **Services**, **Schedules**, and **Architecture**.
Schedules lists live Proxmox backup jobs, PBS prune and verification jobs, the
stack host's live timers, and baseline schedules from their role defaults.
Architecture discovers guests on every monitored Proxmox node, including tenant
machines. Its checkbox includes templates and unmanaged guests. State refreshes
with the homepage collector every minute; the browser reloads it every 30 seconds.
A failed source is named on the page rather than presented as an empty healthy lab.

## Scheduled work

| Work | Schedule | Clock / source |
|---|---|---|
| Guest backups on each node | 02:00 daily, missed runs repeated | Each Proxmox node's local timezone; `playbooks/proxmox.yml` |
| PBS prune | 03:00 daily | ark's local timezone; `roles/pbs/defaults/main.yml` |
| PBS garbage collection | 03:30 daily | ark's local timezone; same file |
| PBS verification | Saturday 04:00, reverify after 30 days | ark's local timezone; same file |
| PBS datastore access guard | Every 15 minutes | Elapsed time; same file |
| Observability snapshot to NAS | Daily, with up to 30 minutes jitter | jwst's local timezone; `roles/observability-stack/defaults/main.yml` |
| Morning ntfy digest | 06:00 daily | jwst's local timezone; same file |
| Backup freshness metrics | Every 15 minutes | Elapsed time; same file |
| Homepage status | Every minute | Elapsed time; `autolab-obs-status.timer` |
| Pending package report | 00:17, 06:17, 12:17, 18:17, plus up to 30 minutes jitter | Each host's local timezone; `roles/updates-report/defaults/main.yml` |
| Container image checks | 08:00 daily | Diun's configured timezone, UTC by default; `roles/container-services/defaults/main.yml` |
| Node heartbeat | Every 5 minutes when its URL is configured | Elapsed time; `roles/proxmox-node/defaults/main.yml` |
| Security upgrades on VMs | Distribution's `apt-daily-upgrade.timer` | OS timer, including randomized delay; inspect the host's live timers |

Role values can be overridden. The homepage distinguishes live jobs from configured
baseline schedules. Node clocks and VM clocks can differ. For example, 02:00
America/Chicago is 08:00 UTC in standard time and 07:00 UTC in daylight time.
Use `systemctl list-timers --all` on a host for its actual next firing.

## Notifications

Grafana evaluates every minute. Each rule's pending duration and repeat interval
appear under Schedules, along with its description and exact Prometheus query.
New groups wait 30 seconds before delivery; changes in an existing group wait
5 minutes. Critical alerts repeat hourly, warnings every 6 hours, and update
reminders every 4 days. Recovery uses the same grouping policy.

Backup freshness uses the PBS snapshot's timestamp, not backup completion.
A running, covered guest with no snapshot newer than 26 hours must remain in
that condition for 30 minutes before paging. New guests get a 26-hour grace
period. Exclusions come from the jobs. A collector failure has its own alert;
a successful new backup, followed by the next metrics collection, clears a
missing-backup alert. Raising the age limit does not repair failed backups.

For recurring failures, run **07 · Proxmox Node**, `playbook=audit`,
`bootstrap=false`. It reads recent backup errors on every node and PBS's own
task logs, and tests snapshot index access as PBS's `backup` user. It does not
change datastore contents. **08 · PBS Backup** runs a guest or the nightly scope
on demand. **09 · PBS Restore** tests whether a snapshot boots.

## Access labels

- **Public + Pocket ID** opens outside Tailscale and requires the named login.
- **Tailscale + Pocket ID** requires both the tailnet and the browser login.
- **Tailscale · app login** leaves login to the application, such as Immich,
  whose mobile API must continue to accept application tokens.
- **Tailscale · direct** names a raw service endpoint. Tailnet policy and the
  service's own authentication govern it; Traefik cannot protect a bypass port.
- **Public · shared links** is intentionally accessible to someone with the
  Immich share link. It does not expose the photo library or admin interface.
- **External · account** opens a third-party console such as GitHub or Tailscale.

Browser routes for Proxmox, PBS and the NAS pass through Pocket ID as well as
those services' own login. Machine APIs, backup transport, telemetry and registry
pushes retain their service credentials or tailnet controls. A browser passkey
challenge is incompatible with those clients.

## Dockhand

Dockhand replaces Portainer on jwst at `dockhand.lab.<zone>`. Traefik requires the
Pocket ID `admins` group. Dockhand's backend has no published port. A small nginx
proxy on the tailnet requires a random, host-generated upstream token which
Traefik adds after login; a direct request receives 403. Neither the token nor
the backend appears in homepage data. The credential remains in root-owned files
on jwst and horizon, and rotates deliberately rather than on every deployment.

The Portainer data volume is retained for rollback; changing the service list
removes its container. The free Dockhand edition gives every authenticated user
full control, so the admin group restriction belongs at the proxy. Compose files
and pinned images remain managed by this repository.

Dockhand is free for homelab use under BSL 1.1, with each release converting to
Apache 2.0 after four years. See the [manual](https://dockhand.pro/manual/) and
[license information](https://dockhand.pro/).
