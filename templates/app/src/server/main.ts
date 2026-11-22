import { Pool } from "pg";
import { createApp } from "./app.js";
import { ensureSchema } from "./db.js";

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
const app = createApp({ database });
app.addHook("onClose", async () => database.end());

try {
  await app.listen({ host: process.env.HOST ?? "127.0.0.1", port: Number(process.env.PORT ?? __SERVER_PORT__) });
} catch (error) {
  app.log.error(error);
  await app.close();
  process.exitCode = 1;
}
