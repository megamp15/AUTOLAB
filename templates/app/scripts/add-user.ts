// Makes an account from the command line and prints its one-time password. This is how the
// first admin exists; after that, admins make accounts in the app.
//
//   npm run user:add -- <email> "<name>" [--admin]

import { Pool } from "pg";
import { createUser } from "../src/server/auth.js";
import { ensureSchema } from "../src/server/db.js";

const [email, name, flag] = process.argv.slice(2);
if (!email || !name) {
  console.error('usage: npm run user:add -- <email> "<name>" [--admin]');
  process.exit(2);
}
const database = new Pool({
  host: process.env.DB_HOST ?? "127.0.0.1",
  port: Number(process.env.DB_PORT ?? 5432),
  database: process.env.DB_NAME ?? "__app__",
  user: process.env.DB_USER ?? "__app__",
  password: process.env.DB_PASSWORD,
});
await ensureSchema(database);
const made = await createUser(database, { email, name, isAdmin: flag === "--admin" });
await database.end();
if (!made) {
  console.error("That email is already in use, or is not an email address.");
  process.exit(1);
}
console.log(`Account made for ${made.user.email}${made.user.isAdmin ? " (admin)" : ""}.`);
console.log(`One-time password: ${made.password}`);
console.log("They will be asked to choose their own when they first sign in.");
