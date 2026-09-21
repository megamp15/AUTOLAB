# ADR-0007: Cloudflare is plumbing; identity is self-hosted

## Status

Accepted — 2026-09-21

## Context

The lab needed to be reachable from anywhere by people the operator names,
with nothing opened on the router and nothing about the lab visible to anyone
not let in. Two things were already true: every service lived on the tailnet
behind the tailnet's own policy, and the operator owned a domain.

Three designs were on the table:

1. **Cloudflare Access in front of a tunnel.** The tunnel hides the lab; Access
   is the login, with an emailed code or a social sign-in. Simple, and it is
   what most tunnel guides do. But Access caps the free plan at fifty seats,
   every login is a code in an inbox, and who may enter is decided in a vendor
   dashboard the repository cannot review.
2. **Tunnel to a reverse proxy with its own identity provider.** The pattern
   a homelab thread described: Traefik with an OIDC plugin, an identity
   provider behind it, Cloudflare Access still in front as a second gate.
3. **The same, without Access.** Cloudflare carries traffic and nothing
   else. Identity lives on a machine in the lab.

The business repository this lab shares a hypervisor with runs a tunnel the
first way: the connector is a container on its largest VM, the token is a
pasted secret, and public hostnames are clicked into the Zero Trust
dashboard. It works, and none of it is a diff.

## Decision

**Cloudflare is plumbing.** The zone's records, the tunnel and its ingress
rules are OpenTofu in `infra/stacks/cloudflare`, applied by their own
workflow. The tunnel token is a sensitive output that the Builder reads from
state; it is never pasted anywhere. Cloudflare Access is not used.

**Identity is self-hosted, on a machine that does nothing else.** `horizon`
runs one compose: `cloudflared`, Traefik and Pocket ID. Pocket ID is the only
login page. Traefik's OIDC plugin logs people in on behalf of anything that
cannot do it itself; anything that speaks OIDC (Grafana, later Proxmox and
PBS) registers its own client and does its own login. One passkey tap, then
every site, for as long as the session is set.

**Passkeys only.** Pocket ID has no password to phish and no code to relay.
Everyone the operator would invite has a device that does passkeys; the
alternatives that offer a password fallback were considered and set aside
for that reason.

**Nothing has a route it was not given.** Cloudflare's catch-all is a 404 from
the connector; Traefik routes only the hostnames in its file; a hostname that
needs a login has no router until its OIDC client exists. Nothing is reachable
without a login, including during setup.

## Consequences

- Adding a public service is a line in `ingress.auto.tfvars` and a router in
  Traefik's dynamic file. Adding a person is an invite link from Pocket ID.
  Neither touches Cloudflare's dashboard.
- Grafana's anonymous viewer went off everywhere the moment it went public. A
  public route plus anonymous viewing is public dashboards; the price is one
  passkey tap for tailnet users too, and the morning digest needed its own
  Grafana token.
- horizon is the one machine deliberately exposed, so it holds nothing worth
  taking: no data of its own except Pocket ID's user database, which is in
  the nightly backup with everything else. Its two generated secrets live and
  die with that database.
- Pocket ID is young. It is small enough to read and it moves fast; versions
  are pinned and swapping the identity provider later is two config files and
  re-inviting users, not a change to the architecture.
- The tunnel is a single connector on a single VM. "Tunnel is down" pages
  after five minutes; the homepage watches the same door from outside every
  minute. The tailnet is unaffected either way.
- Cloudflare Access can be added in front of a single hostname later without
  touching any of this. It was not needed to get here.
