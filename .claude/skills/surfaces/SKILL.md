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

   Neither is generated from the catalog. Everything the owner can open
   from the lab has both a card and a tile: every catalog service with a
   port, every admin or second face of an app (`novaflix-admin`), and every
   outside console the lab depends on (Cloudflare, Tailscale). "Only admins
   use it", "it is tailnet-only" and "the app already has a card" are not
   reasons to leave one off: a page that is on neither is a page the owner
   forgets exists. The only services left off are ones with nothing to
   open, each named with its reason in `NO_PAGE` in
   `scripts/test_every_page_is_listed.py`. That test fails on a catalog
   service with no card or no tile, and on anything listed on one page and
   not the other.
3. A card's access label ("Tailscale + Pocket ID", "Public + Pocket ID") is
   worked out from its URL, so link the one name people use. A service has
   one name: when it moves from `*.lab` to a public name, the card, the
   tile and `CTR_APPS` move with it. An app with a public face and an admin
   face has two names, so two cards and two tiles.
4. A card's `check` runs from jwst against the tailnet address: `http` when
   a health path answers without a login, `tcp` when it answers only to its
   own name or behind a token.
5. `git grep -n -i <name>`, and the old name on a rename or removal. Done
   when every hit is right for the new state.
6. `python3 -m unittest discover -s scripts -p 'test_*.py'` exits 0.
7. List the surfaces touched and skipped in the pull request body.

## After the deploy

home updates by itself when the merge touches the observability role, and
only then. A card switched on by a host's `services` list (an app enabled in
a later pull request than the one that added its card) appears after `05`
`observability` is run by hand: Novaflix ran for a day without its card this
way. dash ships with the `05` `services` run on jwst. Open the name, then home, then
dash. Done when the card and the tile are there, the check is green and the
link opens the app. Between the merge and the services run, home can show a
card for a container that is not up yet: say so in the pull request.
