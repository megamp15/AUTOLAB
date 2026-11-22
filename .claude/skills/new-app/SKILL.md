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
3. **Look.** Change only `apps/web/src/tailwind.css` (colours, corners,
   type) and the wordmark; add components with `npx shadcn@latest add`.
   Before designing a screen, read the owner's reference list in the vault
   (`areas/homelab/ui-component-libraries.md`). Copy the shared shell from
   Novaflix until it is in the template: `theme.tsx` (theme switch that
   follows the device, then remembers), `settings.tsx` (grouped menu),
   `components/ui/ticker.tsx` (numbers that run up). Done when the screens
   have been looked at in dark and light at 393 and 1280 wide.
4. **Sign-in, when anyone but the owner uses it.** Copy from Novaflix:
   `src/server/auth.ts` and `oidc.ts`, their tests, and the tables in
   `db.ts`. Accounts are made by an admin only; Google and Pocket ID sign in
   an email that already has an account. Each provider's redirect address is
   `<PUBLIC_URL>/api/auth/oidc/<google|pocketid>/callback`; the Google client
   is by hand (step list in the app's README), its id and secret arrive
   through `secret`. Done when the copied tests pass and a sign-in with an
   address not on the list is refused.
5. **Register for release.** An entry in `.github/apps.json`, and a default
   `autolab_services_<app>_image_tag: ""` in
   `roles/container-services/defaults/main.yml`. By hand: a read-only deploy
   key on the app's repository, its private half as the secret named in
   `deploy_key`. Give the person the numbered steps from `own-apps.md`.
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
| Google refuses with a redirect mismatch | the address in the browser is not the one registered | open the app at exactly `PUBLIC_URL` |

## Not yet proven

Steps 1 to 4 were done for Novaflix and work locally. No app has been
released through **Release app** or run on its host from these steps; treat
steps 5 to 9 as written from the design, and correct this skill on the first
real release.

## Guardrails

- The public gateway of an app carries no admin page.
- Client secrets and deploy keys travel through `secret`, never through a
  file in either repository or the conversation.
- `main` of the app is what releases; unfinished work stays on its branch.
