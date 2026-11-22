import { Pool } from "pg";
import { createApp } from "./app.js";
import { ensureFirstAdmin } from "./auth.js";
import { ensureSchema } from "./db.js";
import { providersFromEnv } from "./oidc.js";

// Startup: connect to Postgres, create tables, then listen. A missing setting stops the
// process here, not at the first request.
const password = process.env.DB_PASSWORD;
if (!password) throw new Error("DB_PASSWORD is required");

const database = new Pool({
  host: process.env.DB_HOST ?? "127.0.0.1",
  port: Number(process.env.DB_PORT ?? 5432),
  database: process.env.DB_NAME ?? "__app__",
  user: process.env.DB_USER ?? "__app__",
  password,
});

await ensureSchema(database);
// PUBLIC_URL: this app's address as browsers see it, several separated by commas.
const publicUrls = (process.env.PUBLIC_URL ?? "").split(",").map((url) => url.trim().replace(/\/$/, "")).filter(Boolean);
const providers = providersFromEnv(process.env);
const app = createApp({ database, providers, publicUrls });
// FIRST_ADMIN_EMAIL: on an empty database, the owner's account, signed in to through a provider.
if (await ensureFirstAdmin(database, process.env.FIRST_ADMIN_EMAIL, providers.length > 0)) app.log.info("Made the first admin account");
app.addHook("onClose", async () => database.end());

try {
  await app.listen({ host: process.env.HOST ?? "127.0.0.1", port: Number(process.env.PORT ?? __SERVER_PORT__) });
} catch (error) {
  app.log.error(error);
  await app.close();
  process.exitCode = 1;
}
