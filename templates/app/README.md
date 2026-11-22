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

`npm run check` runs lint, types, tests and a build. The tests use the Postgres from `docker compose up -d db`, each in a schema of its own.

`docker compose --profile stack up --build` runs the built images the way they are deployed, on http://127.0.0.1:__STACK_PORT__.

## The web app's look

Screens are built with Tailwind CSS and shadcn/ui components (`apps/web/src/components/ui`). The colours, corners and type of every component come from the variables in `apps/web/src/tailwind.css`. Add a component with `npx shadcn@latest add <name>`; components from Magic UI, Cult UI and Skiper UI install the same way and take the same theme.
