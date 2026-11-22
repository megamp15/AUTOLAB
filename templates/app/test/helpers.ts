import { randomBytes } from "node:crypto";
import { Client } from "pg";
import { ensureSchema, type Database } from "../src/server/db.js";

/**
 * A real, empty Postgres for one test file: its own schema, dropped at the end. Tests run
 * against Postgres itself, so what passes here is what runs. Needs the database from
 * `docker compose up -d db` (or DB_* in the environment).
 */
export async function testDatabase(): Promise<{ database: Database; close: () => Promise<void> }> {
  const client = new Client({
    host: process.env.DB_HOST ?? "127.0.0.1",
    port: Number(process.env.DB_PORT ?? __DB_PORT__),
    database: process.env.DB_NAME ?? "__app__",
    user: process.env.DB_USER ?? "__app__",
    password: process.env.DB_PASSWORD ?? "__app__-dev-password",
  });
  await client.connect();
  const schema = `test_${randomBytes(6).toString("hex")}`;
  await client.query(`CREATE SCHEMA ${schema}`);
  await client.query(`SET search_path TO ${schema}`);
  await ensureSchema(client);
  return {
    database: client,
    close: async () => {
      await client.query(`DROP SCHEMA ${schema} CASCADE`);
      await client.end();
    },
  };
}
