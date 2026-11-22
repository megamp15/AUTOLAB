// Accounts and signing in. An admin makes each account with a password they chose at
// random; the person must replace it the first time they sign in. A browser that has
// signed in holds a session cookie, valid for thirty days.

import { createHash, randomBytes, scrypt, timingSafeEqual } from "node:crypto";
import type { FastifyInstance, FastifyReply, FastifyRequest, preHandlerAsyncHookHandler } from "fastify";
import type { Database } from "./db.js";
import type { Oidc } from "./oidc.js";

export type User = { id: string; email: string; name: string; mustChange: boolean; isAdmin: boolean };

declare module "fastify" {
  interface FastifyRequest {
    /** Who is signed in. Set by `requireUser`. */
    user?: User;
  }
}

const COOKIE = "__app___session";
/** Held between leaving for a provider's login page and coming back: ten minutes. */
const PENDING = "__app___signin";
const SESSION_DAYS = 30;
export const MIN_PASSWORD = 10;

// ---- Passwords: scrypt, with its settings stored beside each hash so they can be raised later.

const SCRYPT = { N: 2 ** 15, r: 8, p: 1, keylen: 64 };
const derive = (password: string, salt: Buffer, options: typeof SCRYPT) =>
  new Promise<Buffer>((resolve, reject) => scrypt(password, salt, options.keylen, { N: options.N, r: options.r, p: options.p, maxmem: 128 * options.N * options.r * 2 }, (error, key) => (error ? reject(error) : resolve(key))));

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const key = await derive(password, salt, SCRYPT);
  return ["scrypt", SCRYPT.N, SCRYPT.r, SCRYPT.p, salt.toString("base64url"), key.toString("base64url")].join("$");
}

export async function verifyPassword(password: string, stored: string | null): Promise<boolean> {
  const [scheme, N, r, p, salt, hash] = (stored ?? "").split("$");
  if (scheme !== "scrypt" || !salt || !hash) return false;
  const expected = Buffer.from(hash, "base64url");
  const actual = await derive(password, Buffer.from(salt, "base64url"), { N: Number(N), r: Number(r), p: Number(p), keylen: expected.length });
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

/** A password to hand to someone once: long, and free of characters that read alike. */
export function randomPassword(): string {
  const letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from(randomBytes(16), (byte) => letters[byte % letters.length]).join("");
}

// ---- Accounts

const toUser = (row: Record<string, unknown>): User => ({ id: String(row["id"]), email: String(row["email"]), name: String(row["name"]), mustChange: Boolean(row["must_change"]), isAdmin: Boolean(row["is_admin"]) });
const normalEmail = (email: string) => email.trim().toLowerCase();
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Makes an account and returns the password to give its owner. Null when the email is taken or
 * malformed. With `password: false` the account has none, and is signed in to through a provider.
 */
export async function createUser(database: Database, input: { email: string; name: string; isAdmin?: boolean; password?: boolean }): Promise<{ user: User; password: string | null } | null> {
  const email = normalEmail(input.email);
  const name = input.name.trim();
  if (!EMAIL.test(email) || email.length > 200 || !name || name.length > 80) return null;
  const password = input.password === false ? null : randomPassword();
  const { rows } = await database.query(
    "INSERT INTO users (email, name, password_hash, must_change, is_admin) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (email) DO NOTHING RETURNING *",
    [email, name, password ? await hashPassword(password) : null, password !== null, Boolean(input.isAdmin)],
  );
  return rows[0] ? { user: toUser(rows[0]), password } : null;
}

/** Gives an account a new random password and signs it out everywhere. Null when there is no such account. */
export async function resetPassword(database: Database, userId: string): Promise<string | null> {
  const password = randomPassword();
  const { rows } = await database.query("UPDATE users SET password_hash = $2, must_change = true WHERE id = $1 RETURNING id", [userId, await hashPassword(password)]);
  if (!rows[0]) return null;
  await database.query("DELETE FROM sessions WHERE user_id = $1", [userId]);
  return password;
}

// ---- Sessions

const hashToken = (token: string) => createHash("sha256").update(token).digest("hex");

async function startSession(database: Database, userId: string): Promise<string> {
  const token = randomBytes(32).toString("base64url");
  await database.query(`INSERT INTO sessions (token_hash, user_id, expires_at) VALUES ($1, $2, now() + interval '${SESSION_DAYS} days')`, [hashToken(token), userId]);
  return token;
}

function readCookie(request: FastifyRequest, wanted = COOKIE): string | null {
  for (const part of (request.headers.cookie ?? "").split(";")) {
    const [name, ...value] = part.trim().split("=");
    if (name === wanted) return value.join("=") || null;
  }
  return null;
}

/** `Secure` whenever the request came over HTTPS (through the proxy), so local development over HTTP still works. */
function sessionCookie(request: FastifyRequest, token: string | null) {
  const secure = request.protocol === "https" ? "; Secure" : "";
  return `${COOKIE}=${token ?? ""}; Path=/; HttpOnly; SameSite=Lax${secure}; Max-Age=${token ? SESSION_DAYS * 86_400 : 0}`;
}
const setCookie = (request: FastifyRequest, reply: FastifyReply, token: string | null) => void reply.header("set-cookie", sessionCookie(request, token));

// ---- Slowing down guesses: after five wrong passwords for an email from one address, a wait.

const WINDOW_MS = 15 * 60_000;
const ALLOWED = 5;

export function createLimiter(now: () => number = Date.now) {
  const misses = new Map<string, number[]>();
  const recent = (key: string) => (misses.get(key) ?? []).filter((at) => now() - at < WINDOW_MS);
  return {
    blocked: (key: string) => recent(key).length >= ALLOWED,
    miss: (key: string) => {
      misses.set(key, [...recent(key), now()]);
      // Old keys are dropped as the map grows, so it cannot be filled from outside.
      if (misses.size > 10_000) for (const other of misses.keys()) if (recent(other).length === 0) misses.delete(other);
    },
    clear: (key: string) => void misses.delete(key),
  };
}

// ---- Routes

export function registerAuth(app: FastifyInstance, database: Database, options: { now?: () => number; oidc?: Oidc; publicUrls?: string[] } = {}) {
  const limiter = createLimiter(options.now);
  const oidc = options.oidc;

  /** Lets a signed-in person through, and refuses everything but a password change while theirs is temporary. */
  const requireUser: preHandlerAsyncHookHandler = async (request, reply) => {
    const token = readCookie(request);
    const { rows } = token
      ? await database.query("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = $1 AND s.expires_at > now()", [hashToken(token)])
      : { rows: [] };
    if (!rows[0]) return reply.code(401).send({ error: "signed_out" });
    request.user = toUser(rows[0]);
    if (request.user.mustChange && !request.url.startsWith("/api/auth/")) return reply.code(403).send({ error: "password_change_required" });
  };
  const requireAdmin: preHandlerAsyncHookHandler = async (request, reply) => {
    if (!request.user?.isAdmin) return reply.code(403).send({ error: "admins_only" });
  };

  // Body: { email, password }. The same answer for a wrong password, an unknown email and an account with no password.
  app.post("/api/auth/login", async (request, reply) => {
    const body = request.body as { email?: unknown; password?: unknown } | null;
    if (typeof body?.email !== "string" || typeof body.password !== "string" || body.password.length > 500) return reply.code(400).send({ error: "invalid_request" });
    const email = normalEmail(body.email);
    const key = `${email}|${request.ip}`;
    if (limiter.blocked(key)) return reply.code(429).send({ error: "too_many_attempts" });
    const { rows } = await database.query("SELECT * FROM users WHERE email = $1", [email]);
    // A hash is checked even for an unknown email, so the time taken does not say which it was.
    const ok = await verifyPassword(body.password, (rows[0]?.["password_hash"] as string | null) ?? UNUSED_HASH);
    if (!rows[0] || !ok) {
      limiter.miss(key);
      return reply.code(401).send({ error: "wrong_email_or_password" });
    }
    limiter.clear(key);
    setCookie(request, reply, await startSession(database, String(rows[0]["id"])));
    return { user: toUser(rows[0]) };
  });

  // ---- Signing in through a provider. Which ones there are, the way out to one, and the way back.

  app.get("/api/auth/providers", async () => ({ providers: oidc?.list() ?? [] }));

  // The provider sends the browser back to the address it left from, when that is one of this
  // app's own (PUBLIC_URL); otherwise to the first of them.
  const callbackFor = (request: FastifyRequest, id: string) => {
    const here = `${request.protocol}://${request.host}`;
    const origin = options.publicUrls?.length ? (options.publicUrls.includes(here) ? here : options.publicUrls[0]!) : here;
    return `${origin}/api/auth/oidc/${id}/callback`;
  };
  const pendingCookie = (request: FastifyRequest, value: string | null) =>
    `${PENDING}=${value ?? ""}; Path=/api/auth/oidc; HttpOnly; SameSite=Lax${request.protocol === "https" ? "; Secure" : ""}; Max-Age=${value ? 600 : 0}`;

  app.get("/api/auth/oidc/:provider", async (request, reply) => {
    const { provider } = request.params as { provider: string };
    if (!oidc?.has(provider)) return reply.code(404).send({ error: "not_found" });
    try {
      const { url, pending } = await oidc.begin(provider, callbackFor(request, provider));
      return reply.header("set-cookie", pendingCookie(request, pending)).redirect(url);
    } catch (error) {
      request.log.error(error);
      return reply.redirect("/?signin=sign_in_failed");
    }
  });

  app.get("/api/auth/oidc/:provider/callback", async (request, reply) => {
    const { provider } = request.params as { provider: string };
    if (!oidc?.has(provider)) return reply.code(404).send({ error: "not_found" });
    const query = request.query as { code?: string; state?: string };
    let result: Awaited<ReturnType<Oidc["finish"]>>;
    try {
      result = await oidc.finish(provider, callbackFor(request, provider), query, readCookie(request, PENDING));
    } catch (error) {
      request.log.error(error);
      result = { error: "sign_in_failed" };
    }
    if ("error" in result) return reply.header("set-cookie", pendingCookie(request, null)).redirect(`/?signin=${result.error}`);
    const token = await startSession(database, result.userId);
    return reply.header("set-cookie", [pendingCookie(request, null), sessionCookie(request, token)]).redirect("/");
  });

  app.post("/api/auth/logout", async (request, reply) => {
    const token = readCookie(request);
    if (token) await database.query("DELETE FROM sessions WHERE token_hash = $1", [hashToken(token)]);
    setCookie(request, reply, null);
    return { signedOut: true };
  });

  app.get("/api/auth/me", { preHandler: requireUser }, async (request) => ({ user: request.user }));

  // Body: { current, next }. Every other browser signed in to the account is signed out.
  app.post("/api/auth/password", { preHandler: requireUser }, async (request, reply) => {
    const body = request.body as { current?: unknown; next?: unknown } | null;
    if (typeof body?.current !== "string" || typeof body.next !== "string" || body.next.length > 500) return reply.code(400).send({ error: "invalid_request" });
    if (body.next.length < MIN_PASSWORD) return reply.code(400).send({ error: "password_too_short", detail: `at least ${MIN_PASSWORD} characters` });
    if (body.next === body.current) return reply.code(400).send({ error: "password_unchanged" });
    const user = request.user!;
    const { rows } = await database.query("SELECT password_hash FROM users WHERE id = $1", [user.id]);
    if (!(await verifyPassword(body.current, (rows[0]?.["password_hash"] as string | null) ?? null))) return reply.code(401).send({ error: "wrong_password" });
    await database.query("UPDATE users SET password_hash = $2, must_change = false WHERE id = $1", [user.id, await hashPassword(body.next)]);
    await database.query("DELETE FROM sessions WHERE user_id = $1", [user.id]);
    setCookie(request, reply, await startSession(database, user.id));
    return { user: { ...user, mustChange: false } };
  });

  // ---- For admins: who has an account, a new one, a reset. The password is shown once, in the answer.

  app.get("/api/admin/users", { preHandler: [requireUser, requireAdmin] }, async () => {
    const { rows } = await database.query("SELECT * FROM users ORDER BY created_at");
    return { users: rows.map(toUser) };
  });

  app.post("/api/admin/users", { preHandler: [requireUser, requireAdmin] }, async (request, reply) => {
    const body = request.body as { email?: unknown; name?: unknown; isAdmin?: unknown; password?: unknown } | null;
    if (typeof body?.email !== "string" || typeof body.name !== "string") return reply.code(400).send({ error: "invalid_request" });
    const made = await createUser(database, { email: body.email, name: body.name, isAdmin: body.isAdmin === true, password: body.password !== false });
    return made ?? reply.code(409).send({ error: "email_taken_or_invalid" });
  });

  app.post("/api/admin/users/:id/reset", { preHandler: [requireUser, requireAdmin] }, async (request, reply) => {
    const { id } = request.params as { id: string };
    if (!/^[0-9a-f-]{36}$/i.test(id)) return reply.code(400).send({ error: "invalid_id" });
    const password = await resetPassword(database, id);
    return password ? { password } : reply.code(404).send({ error: "not_found" });
  });

  // Removes an account with everything of its own; its browsers are signed out at once.
  app.delete("/api/admin/users/:id", { preHandler: [requireUser, requireAdmin] }, async (request, reply) => {
    const { id } = request.params as { id: string };
    if (!/^[0-9a-f-]{36}$/i.test(id)) return reply.code(400).send({ error: "invalid_id" });
    if (id === request.user!.id) return reply.code(400).send({ error: "cannot_remove_yourself" });
    const { rows } = await database.query("DELETE FROM users WHERE id = $1 RETURNING id", [id]);
    return rows[0] ? { removed: true } : reply.code(404).send({ error: "not_found" });
  });

  return { requireUser, requireAdmin };
}

// What an unknown email's password is checked against: a real hash of nothing anyone knows.
const UNUSED_HASH = await hashPassword(randomBytes(24).toString("base64url"));
