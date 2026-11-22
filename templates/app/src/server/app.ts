import Fastify, { type FastifyInstance } from "fastify";
import type { Database } from "./db.js";

export type Dependencies = { database: Database };

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

  return app;
}
