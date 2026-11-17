---
name: observe
description: Hook a machine or a container into AUTOLAB's observability - metrics, logs, alerts, dashboards, the home page. Use for a new VM or service, a new alert or dashboard, or when a host is not reporting.
---

# Observability hookup

Facts, design and traps: `docs/gitops/observability.md`. Prometheus, Loki
and Grafana run on jwst; an agent (Alloy) runs on every managed host.

## What is automatic

- Every Builder machine gets the agent: host metrics and the journal.
- A machine with `docker_enabled` also gets container metrics and logs.
- A new guest appears in the Proxmox panels and on home's Architecture tab
  from the node, with no edit.
- A guest in the nightly backup is watched by *Backup is missing* after a
  26-hour grace.

## What needs a line

| the machine or thing | add |
|---|---|
| in a Stack with no stack host (`edge`) | `observability = { ship_to = "jwst" }` in its `builder` block |
| a tenant's VM | provider-side, over the bridge: `docs/gitops/tenants.md`, "Monitoring" |
| a service with its own metrics endpoint | an entry in `autolab_obs_extra_scrapes` |
| a state worth being woken for | a rule in `roles/observability-stack/templates/alert-rules.yml.j2` |
| a view worth keeping | a dashboard under `grafana/dashboards` |
| a page a person opens | the home card and its `check`: `surfaces` |

## Steps

1. Add the line. `pull-request`.
2. Deploy with `run-workflow`: a change under `roles/observability-*`
   applies on merge for `lab`. A new machine, or one in `edge` or `qnta`,
   needs `05` `observability` dispatched for its environment (after `04`
   when the map changed).
3. Prove the host reports. Done when
   `up{instance=~"<name>.*"}` is 1 in Grafana Explore, and its row on home
   is green.
4. A new alert rule is proven by firing it: cause the condition (or lower
   the threshold for one run), watch it go `pending` then `firing`, see the
   notification arrive, undo it, see it clear. The method and a recorded
   run are in the doc, "Verifying an alert actually fires". A rule that has
   never fired is not done.

## When a host is not reporting

| symptom | cause |
|---|---|
| *Agent is not reporting* for a new machine | `05` `observability` has not run for its environment |
| an agent on the bridge sends nothing | ufw on the stack host: `9009/tcp` and `3101/tcp` from `10.42.0.0/24` |
| logs missing, metrics fine, after a first deploy | the agent started before Loki and gave up: restart `alloy` on the host |
| the alert fires for a guest that is meant to be unmonitored | `agent = false` in another Stack's map does not reach the lab's opt-out list |

## Guardrails

- Grafana, Prometheus and Loki stay on `*.lab`. They are never given a
  public name.
- Dashboards and rules are files in git. One made in Grafana's UI is lost on
  the next deploy.
