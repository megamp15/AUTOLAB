---
tags: [gitops, agents, services, homepage, dash, docs]
status: draft
audience: agent
---

# Definition of done

A change to what the lab runs is done when every **surface** that describes
it agrees with what is deployed. A surface is any place the service or
machine is named for a person to read or click: the pages, the docs, the
agent's skills. Code that deploys and surfaces that still show yesterday is
half a change.

Use this for any pull request that adds, removes, renames or moves a service
or machine, or changes its port, name, login or what an agent may reach.

## Steps

1. Name the change in one line: which service or machine, on which host,
   added, removed, renamed, moved or re-shaped.
2. Walk the surfaces below, top to bottom. For each, edit it or note why it
   does not apply.
3. Run `git grep -n -i <name>` for the service's name, and for the old name
   on a rename or removal. Done when every hit is correct for the new state.
4. Run the repository's tests that read these files:
   `python3 -m unittest discover -s scripts -p 'test_*.py'`.
5. In the pull request body: the surfaces touched, the ones skipped and why,
   and a "To deploy" section with the workflows in order.
6. After the deploy, open the name in a browser, then home and dash. Done
   when the tile is there, its check is green, and the link opens the app.

## Surfaces of a container service

| surface | where | when it applies |
|---|---|---|
| the container | `builders/ansible/roles/container-services/templates/services.d/<name>.yml.j2` | always |
| the catalog: port and login | `autolab_service_catalog` in `builders/ansible/playbooks/group_vars/all.yml` | always |
| where it runs | the machine's `builder.services` in `infra/stacks/<stack>/machines.auto.tfvars` | always |
| told to the lab from another Stack | `autolab_remote_services` in the same `all.yml` | the machine is outside the `lab` Stack |
| secrets | the env block and the Python map in `.github/workflows/05_ansible-builder.yml`, the role's `defaults/main.yml`, `docs/gitops/github-secrets-variables-reference.md` | it reads a secret or variable |
| home: the card | `autolab_obs_homepage_links` in `builders/ansible/roles/observability-stack/defaults/main.yml` | it has a port in the catalog, an admin face included |
| home: container to link | `CTR_APPS` in `builders/ansible/roles/observability-stack/templates/homepage/index.html` | same; the key is the Compose service name |
| home: the AI tab | `aiCard(...)` and `AI_EDGES` in the same `index.html` | an agent gains or loses a source, a credential or a model |
| dash: the tile | `builders/ansible/roles/container-services/templates/dash/services.yaml.j2` | it has a port in the catalog, an admin face included |
| the services table | `docs/gitops/services.md` | always |
| its own page | `docs/gitops/<name>.md` | it needs more than the table row: setup steps, a login, a decision |
| sign-in | `docs/gitops/ingress.md`, "Client configuration as code" | login is `own` through Pocket ID |
| backups | `docs/gitops/backups.md` | it keeps a database or state worth restoring |
| the agent's knowledge | `builders/ansible/roles/container-services/files/hermes/skills/` and `docs/gitops/hermes.md` | Hermes is given a way to read it |

Home and dash are separate pages with separate lists. `home.<label>.<zone>`
is the lab's own page, in the observability role. `dash.<label>.<zone>` is
gethomepage, a container service on jwst. Neither is generated from the
catalog; both are edited by hand, and both are where drift shows first.
Everything the owner can open from the lab is on both, an app's admin face
and outside consoles included. `scripts/test_every_page_is_listed.py` fails
when a catalog service with a port is missing from either, or when the two
pages list different things; a service with nothing to open is named there
with its reason.

A home card's `enabled` reads the machine's services list, so the card
follows the deploy. Its `check` runs from jwst against the tailnet address:
`http` when the service answers a health path without a login, `tcp` when it
answers only to its own name or behind a token.

## Surfaces of a machine or node

The home page's node rows and dash's Proxmox tiles are built from the node
list; they need no edit. What does:

| surface | where |
|---|---|
| the machine | `infra/stacks/<stack>/machines.auto.tfvars` |
| its name | `docs/gitops/naming.md`: nodes by name, services by what they do |
| its page | `docs/gitops/<machine>.md` when it hosts more than one thing |
| the vocabulary | `CONTEXT.md`, when the change adds a term |

## To deploy, in order

- A machines-map change: `03` plan, then `04` apply, before `05` sees it.
- The service: `05`, `playbook: services`, `limit: <host>`, `confirm: check`,
  then `apply`. dash's tiles ship with this run on jwst.
- A new name or port: `05`, `playbook: ingress`.
- Anything under `roles/observability-*`, home included, applies by itself
  on merge. Dispatching `05 observability` as well is a duplicate.

Between the merge and the `05 services` apply, home can show a card for a
container that is not up yet. Say so in the pull request when it matters.

## Removing or renaming

The same surfaces, read as a list of places to delete from. The Compose
project drops a removed container on the next run (`remove_orphans`); the
pages and docs do not drop anything by themselves. On a rename, `CTR_APPS`
is keyed by the Compose service name and breaks silently: the container row
on home loses its link.
