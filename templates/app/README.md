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
