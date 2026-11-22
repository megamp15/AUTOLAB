import assert from "node:assert/strict";
import test from "node:test";
import { createApp } from "../src/server/app.js";
import { testDatabase } from "./helpers.js";

test("status says whether the database answers", async () => {
  const { database, close } = await testDatabase();
  const app = createApp({ database }, { logger: false });
  try {
    assert.deepEqual((await app.inject({ method: "GET", url: "/health/live" })).json(), { status: "ok" });
    assert.deepEqual((await app.inject({ method: "GET", url: "/api/status" })).json(), { application: "__app__", status: "ok", database: "connected" });
    const broken = createApp({ database: { query: async () => { throw new Error("down"); } } }, { logger: false });
    assert.equal((await broken.inject({ method: "GET", url: "/api/status" })).statusCode, 503);
    await broken.close();
  } finally {
    await app.close();
    await close();
  }
});
