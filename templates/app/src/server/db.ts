import type { QueryResult, QueryResultRow } from "pg";

/** The one thing the server needs from Postgres. A `pg` Pool or Client fits it. */
export type Database = { query: <R extends QueryResultRow = QueryResultRow>(text: string, values?: unknown[]) => Promise<QueryResult<R>> };

/** Creates what is missing. Every statement is safe to run again, so this runs on each start. */
export async function ensureSchema(database: Database): Promise<void> {
  await database.query("CREATE TABLE IF NOT EXISTS app_meta (key text PRIMARY KEY, value jsonb NOT NULL)");
}
