---
name: new-app
description: Start an app of our own (its own repository, containers, database and address) from the AUTOLAB template and put it on the lab. Use for a new standalone app, to give an own app its look or sign-in, or to register one for release.
---

# A new app of our own

From nothing to a running, released app on the stack every own app shares:
Fastify, PostgreSQL, React, Tailwind and shadcn/ui. The facts are in
`docs/gitops/own-apps.md`; the worked example is Novaflix
(`docs/gitops/novaflix.md`, repository `megamp15/novaflix`).

A tile inside COSMOS is a different job: the COSMOS repository's
`new-module` skill. Choose an own app when other people sign in to it, or it
has its own address and database.

## Steps

1. **Generate.** `scripts/new-app.sh <name> <directory> [port-base]`, with a
   port base no other app uses. Done when `npm run check` passes in the new
   directory and `docker compose --profile stack up --build` serves the
   starter page from the two built images.
2. **Repository.** A private GitHub repository under the owner's account,
   `main` pushed, all later work on `feature/<name>` branches through pull
   requests. Done when its CI run is green.
3. **Make it this app's own.** The template is already a whole small app
   (accounts, sign-in, Settings, the theme, an opening screen); what changes
   per app is listed in `own-apps.md`, "The template". In
   `apps/web/src/`: the colours in `tailwind.css`; `NAME` and `ACCENT_FROM`
   in `theme.tsx`; the centrepiece in `centrepiece.tsx`, drawn from the
   brief in the comment at its top, and `loader.tsx` to match it; the three
   words passed to `Intro` in
   `main.tsx`; `backdrop.tsx` when stars do not suit. Before designing a
   screen, read the owner's reference list in the vault
   (`areas/homelab/ui-component-libraries.md`); add components with
   `npx shadcn@latest add`. Done when the opening screen, sign-in and
   Settings have been looked at in dark and light at 393 and 1280 wide, and
   the way in has been watched, not only screenshotted.
4. **Sign-in providers, when anyone but the owner uses it.** The code is in
   the template; each provider is switched on by its settings. The redirect
   address is `<PUBLIC_URL>/api/auth/oidc/<google|pocketid>/callback`. The
   Google client is by hand (console.cloud.google.com: Google Auth Platform,
   a Web application client with that redirect address, then Audience,
   Publish app); its id and secret arrive through `secret`. Name the
   Google project's consent screen after the app, or give the app its own
   project: the name on Google's screen is the project's, shared by every
   client in it. The Pocket ID client is code: a line for the app in
   `managed-pocketid-policy.json.j2` and `POCKETID_*` in the server's
   environment, as Novaflix has (`pocket-id` skill). The first account is
   code too: `FIRST_ADMIN_EMAIL` in the server's environment, set from
   `autolab_services_admin_email`, makes it on an empty database. Done when a
   sign-in with an address not under User access comes back refused.
5. **Register for release.** An entry in `.github/apps.json`, and a default
   `autolab_services_<app>_image_tag: ""` in
   `roles/container-services/defaults/main.yml`. By hand: a read-only deploy
   key on the app's repository, its private half as the secret named in
   `deploy_key`. Give the person the numbered steps from `own-apps.md`.
   Then the steps in "An app that releases itself" there, so a push to the
   app's `main` releases without a run started by hand: one key to generate
   and four commands, the person's to do. Until they have, release by hand.
6. **Define the service** with `service`, in Novaflix's shape: a compose
   fragment with database, server and gateway on an internal network, the
   database password generated on the host, a catalog entry, the database in
   the shared dump. Leave the app off every machine's `services` list in
   this pull request: the role refuses to start it without a pinned image.
7. **Name it** with `route`. Tailnet-only is the default. A public name
   needs the owner to say so; then the app's own sign-in is the door
   (`login: own`, `lab: false`), and anything an admin does is served only
   by a second gateway on a `*.lab` name behind the passkey
   (`novaflix.md`, "Why two gateways").
8. **Release and enable.** `pull-request` for steps 5 to 7. Then
   `run-workflow`: **Release app** with the app and a commit on its `main`.
   Then a second pull request adding the app to its host's `services` list,
   and `05` with `services`, then `ingress`; `10` for a public name.
9. `surfaces`: the home card, the dash tile and the docs agree with what
   runs.

## Proof

- The app's address answers its sign-in or starter page from outside the
  host; `/api/status` reports `database: connected`.
- For a public app: the public name answers 404 for `/api/admin/`, and the
  `*.lab` admin name answers 401 before sign-in.

## When it goes wrong

| symptom | cause | fix |
|---|---|---|
| shadcn's CLI cannot place a component | it reads the `@/` path from the root `tsconfig.json` | keep that file; it exists only for the CLI |
| a theme rule has no effect on a shadcn component | the rule is in a layer and the component's own utility classes win | write the override outside any `@layer` |
| a provider button is missing on the sign-in page | its client id or secret is not in the server's environment | set both, and `PUBLIC_URL` |
| `05` `ingress` apply fails at "Reconcile declared Pocket ID clients" with `HTTP 404`, Ansible itself green | Traefik had just restarted for the new route and the login service was briefly unreachable | re-run the failed job |
| Google's screen names another app | the OAuth client is in a Google project whose consent screen has that name | rename it under Google Auth Platform, Branding, or make the client in a project of the app's own |
| the Pocket ID button is missing after a deploy | the services run had no `POCKETID_API_KEY` (only `edge` and `lab` services runs get it), or the app has no line in the managed policy | add the line, or the environment in `05`'s condition |
| the app's CI has no `release` job run | `RELEASE_APP_CLIENT_ID` is not set on its repository | `own-apps.md`, "An app that releases itself" |
| Google refuses with a redirect mismatch | the address in the browser is not the one registered | open the app at exactly `PUBLIC_URL` |

## How far this is proven

All nine steps were done for Novaflix, which was released and deployed with
them on 2026-11-22. A second app has not yet been taken through them.

## Guardrails

- The public gateway of an app carries no admin page.
- Client secrets and deploy keys travel through `secret`, never through a
  file in either repository or the conversation.
- `main` of the app is what releases; unfinished work stays on its branch.
