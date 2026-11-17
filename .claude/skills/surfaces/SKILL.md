---
name: surfaces
description: Make home, dash and the docs match what is deployed. Use whenever a service or machine is added, removed, renamed, moved, or changes its port, name, login or who can reach it.
---

# Surfaces

A surface is any place a service or machine is named for a person to read or
click. The list, with paths, is `docs/gitops/definition-of-done.md`. Walk it;
this is how.

## Steps

1. Say the change in one line: which service or machine, on which host,
   added, removed, renamed, moved or re-shaped.
2. Open `docs/gitops/definition-of-done.md` and go down its table. For each
   row edit the surface, or write down why it does not apply. The two that
   are forgotten:
   - **home** (`home.lab.<zone>`): the card in `autolab_obs_homepage_links`,
     and the container-to-link map `CTR_APPS` in the page's `index.html`,
     keyed by the Compose service name.
   - **dash** (`dash.lab.<zone>`): the tile in `dash/services.yaml.j2`.

   Neither is generated from the catalog. A service with a page a person
   opens has both; a service without one has neither.
3. A card's access label ("Tailscale + Pocket ID", "Public + Pocket ID") is
   worked out from its URL, so link the one name people use. A service has
   one name: when it moves from `*.lab` to a public name, the card, the
   tile and `CTR_APPS` move with it.
4. A card's `check` runs from jwst against the tailnet address: `http` when
   a health path answers without a login, `tcp` when it answers only to its
   own name or behind a token.
5. `git grep -n -i <name>`, and the old name on a rename or removal. Done
   when every hit is right for the new state.
6. `python3 -m unittest discover -s scripts -p 'test_*.py'` exits 0.
7. List the surfaces touched and skipped in the pull request body.

## After the deploy

home updates by itself when the merge touches the observability role. dash
ships with the `05` `services` run on jwst. Open the name, then home, then
dash. Done when the card and the tile are there, the check is green and the
link opens the app. Between the merge and the services run, home can show a
card for a container that is not up yet: say so in the pull request.
