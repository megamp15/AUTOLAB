---
tags: [gitops, pocket-id, identity, passkey, oidc, groups]
status: active
audience: operator
---

# Pocket ID

Pocket ID on horizon signs people in with a passkey. Its configuration is
declared in this repository. Its people are not: you add a user and choose
their groups in Pocket ID, and nothing here overwrites that.

For how it is deployed and how a login reaches a page, see
[ingress](./ingress.md).

## What is code and what is by hand

| thing | where | applied by |
|---|---|---|
| which groups exist | `allowedUserGroups` lists in `builders/ansible/pocketid-clients.json`: a group named there is created | `05` `ingress` (Traefik, Proxmox, Immich); `05` `observability` (Grafana) |
| which groups may sign in through a client | the same lists | same |
| Traefik's and Grafana's callback, logout and launch URLs | the same file | same |
| which groups open which name | the route: `autolab_ingress_homepage_groups` in the ingress role, `groups` on a public route in `playbooks/ingress.yml` | `05` `ingress` |
| the apps' own clients (named `AUTOLAB <app>`): created, secret generated, restricted to `admins`, deleted when the app is removed | `templates/managed-pocketid-policy.json.j2` in the container-services role | `05` `services`, on the machine the app runs on (`edge`; `lab` for Novaflix once switched on, `novaflix.md`) |
| users, and who is in which group | Pocket ID, *Users* and *User Groups* | by hand |
| passkeys | the person's device or password manager | by hand; cannot be code |
| the first admin and the API key | Pocket ID's one-time setup, then *API Keys* | by hand; code needs them to start |
| the secrets of Traefik, Grafana, Proxmox and Immich | Pocket ID → the client → *Generate*, then GitHub secrets (Immich: its own settings page) | by hand |
| Proxmox's and Immich's URLs | Pocket ID, the client | by hand |

The last two are by hand on purpose. Creating those four clients from nothing
would mean a CI credential that can write GitHub secrets, in a public
repository, to save ten minutes in a rebuild that a restore makes
unnecessary.

Groups are never deleted from code, and a group's members are never read or
changed. A client's allowed groups are replaced by its list: a group allowed
by hand and not listed is removed from that client on the next apply.

## Who may open what

| group | signs in through | opens |
|---|---|---|
| `admins` | every client | everything |
| `paradigm` | Traefik only | `qr.<zone>` only |

A user in no group is refused by Pocket ID at every client. `viewers` exists
in Pocket ID from the first setup and is allowed nowhere; to use it again,
add it to the Traefik client's list.

Two locks, both needed: the client's list decides who Pocket ID will sign in,
the route's groups decide which name that login opens. `paradigm` is on the
Traefik client, which fronts every `*.lab` name too; it opens only `qr`
because no other route names it, and every route checks its groups on each
request.

## Changing the code side

| to | edit | then run |
|---|---|---|
| add a group, or let a group use a client | the client's `allowedUserGroups` in `pocketid-clients.json` | `05` `ingress`, check then apply (`observability` for Grafana) |
| let a group open a name | the route's groups | `05` `ingress` |
| put a new name on the internet behind the passkey | [ingress](./ingress.md), "A public name behind the passkey" | `05` `ingress`, then `10 - Cloudflare` |
| give a new app its own login | a line in `managed-pocketid-policy.json.j2` | `05` `services` on the app's machine |
| adopt another hand-made client | an entry with `"name": "<its name in Pocket ID>"` and its groups | `05` `ingress` |

Check mode prints what would change and writes nothing: `group X would be
created`, `allowed groups would change`. Read it before `apply`. The order
inside an apply is fixed so that no step leaves a client admitting nobody:
groups first, the restriction last.

The runs need the repository secret `POCKETID_API_KEY`. The key expires;
renew it in Pocket ID (*API Keys*) and update the secret before it does, or
the run stops with `Pocket ID GET failed with HTTP 401`.

## By hand: add a person

1. `https://auth.<zone>` → *Users* → *Add User*: a username, a name, an
   email. For a shared account (one login for a business), name it for the
   business.
2. On the same form, or *User Groups* → the group → add them: only the groups
   they need. Someone who should open one page gets that page's group and no
   other.
3. The user's row → the menu → *Login Code*. It is a link that signs them in
   once, without a passkey, so they can register one. Pick a short lifetime.
4. They open the link and register a passkey. To keep it in a particular
   Bitwarden vault (a business's, not yours): open the link in a browser
   where that vault is the one unlocked, and when the passkey prompt appears,
   choose Bitwarden's *Save passkey* rather than the device's own.
5. They open the page. A 403 from Traefik means the passkey worked and the
   group is wrong; Pocket ID's own "not allowed" page means the group is not
   on the client's list.

## By hand: take access away

Remove the user from the group, or delete the user. Their open session keeps
working until its token next renews; deleting the user ends it at that
renewal too. For "now", also delete the user's passkeys.

## Recreating it

The quick way is the nightly backup of horizon: a restore brings back users,
passkeys, groups, clients and secrets together, and every login keeps
working.

From nothing, in order: the ingress run brings up an empty Pocket ID; you do
the one-time setup, create an API key, and create the four hand-made clients
(their names, callbacks and secrets are in [ingress](./ingress.md)); the next
ingress run creates the groups and sets every client's groups; the `services`
run recreates the apps' clients. Everyone registers a new passkey: a passkey
is bound to the database that issued it.
