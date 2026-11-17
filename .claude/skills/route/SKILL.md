---
name: route
description: Give something a name in AUTOLAB - a *.lab name on the tailnet, or a public name on the internet with or without the passkey. Use to expose a service, a machine's own UI, a NAS app, or to take a name away.
---

# A name for something

How ingress works, and the proofs: `docs/gitops/ingress.md`. horizon runs
Traefik; `*.lab.<zone>` exists only inside the tailnet; public names come
through the Cloudflare tunnel.

## Which kind

| the thing | where the route is declared |
|---|---|
| a catalog service on the services host or nebula | nowhere: the catalog entry is the route (`service`) |
| a machine's own UI (a node, PBS, the NAS) | the ingress role's host lists in `roles/ingress/defaults/main.yml` |
| an app in the NAS's own Docker | `autolab_ingress_nas_apps` |
| something in another Stack the lab inventory cannot see | `autolab_ingress_extra_routes` in `playbooks/ingress.yml` |
| public, no login (a shared link) | `autolab_ingress_public_routes`, plus the label in `infra/stacks/cloudflare/ingress.auto.tfvars` |
| public under the Paradigm Prints domain | the container joins the `paradigm-public` network; the hostname is added by hand in that Cloudflare account (`docs/gitops/qr.md`, "The Paradigm tunnel"). Nothing sits in front of it, so only a container that is safe to be public |
| public, behind the passkey | the same, with `groups`, and `lab: false` on its catalog entry so it has one name: `docs/gitops/ingress.md`, "A public name behind the passkey" |

Names: a hypervisor by its node name, everything else by what it is
(`pbs`, `nas`, `home`), never by the machine it happens to be on.

## Steps

1. Default to `*.lab`. A public name needs the user to say so, and a reason
   someone off the tailnet must reach it. Operator pages never get one.
2. Choose the login: the app's own when it has one and speaks Pocket ID;
   the plugin when it has none; `admin` plus an upstream token when being
   signed in is not enough. Which groups: `pocket-id`.
3. Edit the declaration. For a public name also add the label to
   `ingress.auto.tfvars`, and update the allowlist the test pins in
   `scripts/test_private_dashboards.py`: that test is the gate that keeps
   names from going public by accident, so changing it is the decision.
4. `surfaces`, `pull-request`.
5. `run-workflow`: `05` `ingress` (`environment=lab`); for a public name
   then `10` plan and apply. Either order is safe: a record with no route
   answers 404.

## Proof

- Tailnet name: `curl -sI https://<name>.lab.<zone>` from a tailnet machine
  shows a valid certificate; signed out it is 401 (plugin) or the app's
  login; `http://` answers 301.
- Public name: from off the tailnet, signed out, 401; a person in the group
  reaches the page; a person outside it gets 403.
- Not public: `dig <name>.lab.<zone>` from outside answers nothing.

## Taking a name away

Remove the declaration, and the label for a public one; `05` `ingress`,
then `10`. A name in DNS with no route answers 404, so the order is safe.

## Guardrails

- A route never points at something that answers anyone who reaches its
  port, unless that is the point (a shared link).
- A raw tailnet port is a way around Traefik. A page that must be
  admin-only also refuses requests that lack Traefik's token.
