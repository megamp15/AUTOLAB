import type { QueryResult, QueryResultRow } from "pg";

/** The one thing the server needs from Postgres. A `pg` Pool or Client fits it. */
export type Database = { query: <R extends QueryResultRow = QueryResultRow>(text: string, values?: unknown[]) => Promise<QueryResult<R>> };

/** Creates what is missing. Every statement is safe to run again, so this runs on each start. */
export async function ensureSchema(database: Database): Promise<void> {
  await database.query("CREATE TABLE IF NOT EXISTS app_meta (key text PRIMARY KEY, value jsonb NOT NULL)");
  // People. There is no sign-up: an admin makes each account. `must_change` is set while the
  // password is one somebody else chose (a new account, or a reset).
  await database.query(`
    CREATE TABLE IF NOT EXISTS users (
      id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      email         text NOT NULL UNIQUE,
      name          text NOT NULL,
      password_hash text,
      must_change   boolean NOT NULL DEFAULT true,
      is_admin      boolean NOT NULL DEFAULT false,
      created_at    timestamptz NOT NULL DEFAULT now()
    )
  `);
  // A signed-in browser. Only the token's hash is kept, so a copy of this table signs nobody in.
  await database.query(`
    CREATE TABLE IF NOT EXISTS sessions (
      token_hash text PRIMARY KEY,
      user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
      created_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL
    )
  `);
  await database.query("CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id)");
  // A person's id at a sign-in provider (Google, Pocket ID), tied to their account the first
  // time they sign in that way.
  await database.query(`
    CREATE TABLE IF NOT EXISTS user_identities (
      provider   text NOT NULL,
      subject    text NOT NULL,
      user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (provider, subject)
    )
  `);
}
