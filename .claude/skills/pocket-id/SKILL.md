---
name: pocket-id
description: Pocket ID access changes in AUTOLAB. Use when adding or removing a group, deciding which group opens which page, putting a page behind the passkey, giving an app its own login, adding or removing a user, or when a login is refused.
---

# Pocket ID access

The map of what is declared where, and the reasons, is
`docs/gitops/pocket-id.md`. Read it first; this skill is the procedure.

Sort the request into one **side** before touching anything:

- **Code side**: groups that exist, which groups a client admits, URLs, which
  groups a route opens, an app's own client. You change it by pull request.
- **Hand side**: users, group membership, passkeys, the API key, the secrets
  of the four hand-made clients (Traefik, Grafana, Proxmox, Immich). The
  user does these in Pocket ID. You give them the steps from
  `docs/gitops/pocket-id.md` ("By hand: ...") with their real names filled
  in, and you say plainly that it cannot be done from here.

A request often has both sides ("let Sam open the QR page" is a group on the
code side, if new, and a user on the hand side). Do the code side, then hand
over the hand side as numbered steps.

## Code side

1. Find the row for the change in "Changing the code side" in
   `docs/gitops/pocket-id.md`. It names the file and the run.
2. Make the edit. Two locks decide access and a change usually needs both:
   the client's `allowedUserGroups` (who Pocket ID signs in) and the route's
   groups (which name that login opens). A group on the client and on no
   route opens nothing; a group on a route and not on the client is refused
   by Pocket ID.
3. Check least privilege: a new group is named on exactly the routes it is
   for. `grep -rn "<group>" builders/ansible docs/gitops` shows every place.
4. Run `python3 -m unittest discover -s scripts -p 'test_*.py'`. Done when it
   exits 0. `test_private_dashboards.py` and `test_pocketid_clients.py` pin
   the public allowlist and the declared groups: a deliberate change there
   means updating the test in the same commit.
5. Open the pull request with a "To deploy" section listing the runs in
   order.
6. After merge, when the user asks for the deploy, run check mode first and
   read its Pocket ID lines before applying:

   ```
   gh workflow run 05_ansible-builder.yml -f environment=lab -f playbook=ingress -f confirm=check
   gh workflow run 05_ansible-builder.yml -f environment=lab -f playbook=ingress -f confirm=apply
   ```

   | changed | run |
   |---|---|
   | Traefik, Proxmox or Immich in `pocketid-clients.json`; any route | `05`, `lab`, `ingress` |
   | Grafana in `pocketid-clients.json` | `05`, `lab`, `observability` |
   | a public hostname | `05` `ingress`, then `10_cloudflare.yml -f confirm=apply` |
   | `managed-pocketid-policy.json.j2` | `05`, `edge`, `services`, limit the apps host |

   Done when the apply's log shows `allowed groups applied` or `unchanged`
   for each client, and the proof below passes.

## Proof

- Signed out, non-browser: `curl -s -o /dev/null -w '%{http_code}' https://<name>/` is 401.
- A user in the group reaches the page. The user does this; ask them.
- A user outside it gets 403 from Traefik, or Pocket ID's refusal.

## When a login is refused

| what they see | cause | side |
|---|---|---|
| Pocket ID says the user may not use this app | the user's group is not in the client's `allowedUserGroups`, or the user is in no group | code, or hand |
| 403 after a successful passkey | signed in, but the route does not name their group | code |
| 404 | the route does not exist: the name is missing from `playbooks/ingress.yml`, or the plugin's client is not configured | code |
| Cloudflare error page | no DNS record or tunnel rule: `10 - Cloudflare` not applied | code |
| the run fails with `HTTP 401` from Pocket ID | `POCKETID_API_KEY` expired | hand |
| `Expected exactly one Pocket ID client named X` | a hand-made client was renamed or deleted in Pocket ID | hand |

## Guardrails

- `admins` stays in every client's list. A list without it locks the owner
  out of that client.
- Operator pages (home, Grafana, Prometheus, Proxmox) stay on `*.lab`. A
  public name behind the passkey is for a page someone off the tailnet
  needs, and only on the user's say-so.
- Merging to `main` can deploy. Dispatch a run only when asked.
