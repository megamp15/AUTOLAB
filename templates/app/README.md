# __App__

__App__. Fastify, PostgreSQL, React.

## Run it

Node 24 and Docker.

```sh
cp .env.example .env
docker compose up -d db
npm install
npm run dev:server   # the API, on :__SERVER_PORT__
npm run dev:web      # the app, on http://127.0.0.1:__WEB_PORT__
```

There is no sign-up. Make the first account from the command line; it prints a one-time password, which the app asks you to replace when you first sign in:

```sh
npm run user:add -- you@example.com "Your Name" --admin
```

An admin makes everyone else's account inside the app, in Settings under User access.

A deployment needs no command: with `FIRST_ADMIN_EMAIL` set and a sign-in provider configured, the server makes that admin account, without a password, the first time it starts on an empty database.

## Releasing

A push to `main` that passes CI starts AUTOLAB's **Release app**, which publishes the images, pins the tag and deploys. The `release` job in `.github/workflows/ci.yml` does it with a GitHub App that may only start workflows in AUTOLAB: its client ID is the repository variable `RELEASE_APP_CLIENT_ID`, and its private key is the secret `RELEASE_APP_KEY` in the `release` environment, which only `main` can read. Without the variable the job is skipped.

`npm run check` runs lint, types, tests and a build. The tests use the Postgres from `docker compose up -d db`, each in a schema of its own.

`docker compose --profile stack up --build` runs the built images the way they are deployed, on http://127.0.0.1:__STACK_PORT__.

## Signing in

There is no sign-up. An admin adds each person by email in Settings, under User access, and only those people can sign in, in one of these ways:

- **Email and password.** The admin is shown a one-time password to pass on; the person replaces it the first time they sign in.
- **Google or Pocket ID** (each shown only when it is set up). The provider proves which email the person owns, and they are let in only if an account already has that email. Nobody else gets an account. A person added with "Password" unticked signs in this way only.

The first sign-in through a provider ties that provider's id for the person to their account; from then on the id is what matches. Google's email must be marked verified. Pocket ID's is taken as given, because the owner makes its accounts.

To set a provider up, give it the redirect address `<PUBLIC_URL>/api/auth/oidc/<google|pocketid>/callback` and put its client id and secret in the environment (see `.env.example`). `PUBLIC_URL` is this app's address as browsers see it; several are separated by commas.

## The web app's look

Screens are built with Tailwind CSS and shadcn/ui components (`apps/web/src/components/ui`). The whole look is `apps/web/src/tailwind.css`: light and dark colours, sharp corners, mono capitals for labels and controls, and one neon colour. Dark or light follows the device until the switch in the header is used, which is remembered per browser. `Ticker` (`components/ui/ticker.tsx`) is the number that runs up to its value. Add a component with `npx shadcn@latest add <name>`; components from Magic UI, Cult UI and Skiper UI install the same way and take the same theme.

## The opening screen

Before sign-in there is one screen to come in through, on every load: a heads-up-display frame, a centrepiece, one button and a status line (`apps/web/src/intro.tsx`). The centrepiece (`centrepiece.tsx`) is the app's own drawing; the comment at its top is the brief for drawing one. The centrepiece leans toward the pointer. Pressing the button plays the centrepiece's exit, and the sign-in panel then switches on (`Boot` in `theme.tsx`). The backdrop behind every screen is `backdrop.tsx`. A wait that lasts long enough to notice shows the app's own loader (`loader.tsx`, with the same kind of brief at its top).
