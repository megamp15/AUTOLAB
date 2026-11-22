import Fastify, { type FastifyInstance } from "fastify";
import { registerAuth } from "./auth.js";
import type { Database } from "./db.js";
import { createOidc, type Fetcher, type OidcProvider } from "./oidc.js";

export type Dependencies = {
  database: Database;
  /** The clock, for tests. */
  now?: () => number;
  /** Other ways to sign in (Google, Pocket ID). */
  providers?: OidcProvider[];
  /** This app's own addresses, for the way back from a provider. */
  publicUrls?: string[];
  /** Calls to providers, for tests. */
  fetcher?: Fetcher;
};

export function createApp(dependencies: Dependencies, options: { logger?: boolean } = {}): FastifyInstance {
  const app = Fastify({ logger: options.logger ?? true, trustProxy: true });

  // For the container's health check: the process is up.
  app.get("/health/live", async () => ({ status: "ok" }));

  // The process is up and can reach its database.
  app.get("/api/status", async (_request, reply) => {
    try {
      await dependencies.database.query("SELECT 1");
      return { application: "__app__", status: "ok", database: "connected" };
    } catch {
      return reply.code(503).send({ application: "__app__", status: "degraded", database: "unreachable" });
    }
  });

  const { database, now, fetcher, publicUrls } = dependencies;
  const oidc = dependencies.providers?.length ? createOidc(dependencies.providers, database, { ...(fetcher ? { fetcher } : {}), ...(now ? { now } : {}) }) : undefined;
  registerAuth(app, database, { ...(now ? { now } : {}), ...(oidc ? { oidc } : {}), ...(publicUrls ? { publicUrls } : {}) });

  return app;
}
