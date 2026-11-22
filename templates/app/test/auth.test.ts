import assert from "node:assert/strict";
import test from "node:test";
import { createApp } from "../src/server/app.js";
import { createLimiter, createUser, ensureFirstAdmin, hashPassword, randomPassword, verifyPassword } from "../src/server/auth.js";
import { testDatabase } from "./helpers.js";

const json = { "content-type": "application/json" };
const cookieOf = (response: { headers: Record<string, unknown> }) => String(response.headers["set-cookie"]).split(";")[0]!;

test("a password is kept as a salted hash and checked against it", async () => {
  const hash = await hashPassword("correct horse battery");
  assert.match(hash, /^scrypt\$32768\$8\$1\$/);
  assert.notEqual(hash, await hashPassword("correct horse battery"), "salted: the same password hashes differently each time");
  assert.equal(await verifyPassword("correct horse battery", hash), true);
  assert.equal(await verifyPassword("correct horse batterx", hash), false);
  assert.equal(await verifyPassword("anything", null), false);
  assert.equal(await verifyPassword("anything", "not a hash"), false);
  assert.match(randomPassword(), /^[a-zA-Z2-9]{16}$/);
});

test("guesses are slowed after five misses, per email and address, for fifteen minutes", () => {
  let clock = 0;
  const limiter = createLimiter(() => clock);
  for (let attempt = 0; attempt < 5; attempt += 1) limiter.miss("a|1");
  assert.equal(limiter.blocked("a|1"), true);
  assert.equal(limiter.blocked("a|2"), false);
  clock = 15 * 60_000 + 1;
  assert.equal(limiter.blocked("a|1"), false);
});

test("an account is made by an admin, signs in, and must choose a password before anything else", async () => {
  const { database, close } = await testDatabase();
  const app = createApp({ database }, { logger: false });
  try {
    const admin = (await createUser(database, { email: "Owner@Example.com", name: "Owner", isAdmin: true }))!;
    assert.equal(admin.user.email, "owner@example.com");
    assert.equal(await createUser(database, { email: "owner@example.com", name: "Again" }), null, "one account per email");
    assert.equal(await createUser(database, { email: "not-an-email", name: "X" }), null);

    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me" })).statusCode, 401);
    const wrong = await app.inject({ method: "POST", url: "/api/auth/login", headers: json, payload: { email: "owner@example.com", password: "nope" } });
    const unknown = await app.inject({ method: "POST", url: "/api/auth/login", headers: json, payload: { email: "nobody@example.com", password: "nope" } });
    assert.deepEqual([wrong.statusCode, wrong.json(), unknown.statusCode, unknown.json()], [401, { error: "wrong_email_or_password" }, 401, { error: "wrong_email_or_password" }]);

    const login = await app.inject({ method: "POST", url: "/api/auth/login", headers: json, payload: { email: " OWNER@example.com ", password: admin.password } });
    assert.equal(login.statusCode, 200);
    assert.match(String(login.headers["set-cookie"]), /^__app___session=[\w-]{43}; Path=\/; HttpOnly; SameSite=Lax; Max-Age=2592000$/);
    let cookie = cookieOf(login);

    // With a password somebody else chose, only the account's own pages answer.
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie } })).json().user.mustChange, true);
    assert.deepEqual((await app.inject({ method: "GET", url: "/api/admin/users", headers: { cookie } })).json(), { error: "password_change_required" });

    const change = (payload: object) => app.inject({ method: "POST", url: "/api/auth/password", headers: { ...json, cookie }, payload });
    assert.equal((await change({ current: admin.password, next: "short" })).json().error, "password_too_short");
    assert.equal((await change({ current: "wrong", next: "a long enough one" })).statusCode, 401);
    assert.equal((await change({ current: admin.password, next: admin.password })).json().error, "password_unchanged");
    const changed = await change({ current: admin.password, next: "a long enough one" });
    assert.equal(changed.json().user.mustChange, false);
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie } })).statusCode, 401, "the old session is ended");
    cookie = cookieOf(changed);

    // Now the admin can make an account for a friend, who gets a one-time password.
    const made = await app.inject({ method: "POST", url: "/api/admin/users", headers: { ...json, cookie }, payload: { email: "friend@example.com", name: "Friend" } });
    assert.equal(made.statusCode, 200);
    assert.equal(made.json().user.mustChange, true);
    const friend = await app.inject({ method: "POST", url: "/api/auth/login", headers: json, payload: { email: "friend@example.com", password: made.json().password } });
    const friendCookie = cookieOf(friend);
    const friendChanged = await app.inject({ method: "POST", url: "/api/auth/password", headers: { ...json, cookie: friendCookie }, payload: { current: made.json().password, next: "my own password" } });
    assert.equal((await app.inject({ method: "GET", url: "/api/admin/users", headers: { cookie: cookieOf(friendChanged) } })).statusCode, 403, "a friend is not an admin");
    assert.equal((await app.inject({ method: "GET", url: "/api/admin/users", headers: { cookie } })).json().users.length, 2);

    // A reset gives a new one-time password and signs the account out.
    const reset = await app.inject({ method: "POST", url: `/api/admin/users/${made.json().user.id}/reset`, headers: { cookie } });
    assert.match(reset.json().password, /^[a-zA-Z2-9]{16}$/);
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie: cookieOf(friendChanged) } })).statusCode, 401);

    // Removing an account ends its access; an admin cannot remove their own.
    const again = await app.inject({ method: "POST", url: "/api/auth/login", headers: json, payload: { email: "friend@example.com", password: reset.json().password } });
    assert.equal(again.statusCode, 200);
    assert.equal((await app.inject({ method: "DELETE", url: `/api/admin/users/${admin.user.id}`, headers: { cookie } })).json().error, "cannot_remove_yourself");
    assert.deepEqual((await app.inject({ method: "DELETE", url: `/api/admin/users/${made.json().user.id}`, headers: { cookie } })).json(), { removed: true });
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie: cookieOf(again) } })).statusCode, 401);
    assert.equal((await app.inject({ method: "DELETE", url: `/api/admin/users/${made.json().user.id}`, headers: { cookie } })).statusCode, 404);

    const out = await app.inject({ method: "POST", url: "/api/auth/logout", headers: { cookie } });
    assert.match(String(out.headers["set-cookie"]), /Max-Age=0/);
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie } })).statusCode, 401);
  } finally {
    await app.close();
    await close();
  }
});

test("signing in is refused after five wrong passwords, even with the right one", async () => {
  const { database, close } = await testDatabase();
  const app = createApp({ database, now: () => 1_000 }, { logger: false });
  try {
    const made = (await createUser(database, { email: "a@example.com", name: "A" }))!;
    const attempt = (password: string) => app.inject({ method: "POST", url: "/api/auth/login", headers: json, payload: { email: "a@example.com", password } });
    for (let index = 0; index < 5; index += 1) assert.equal((await attempt("wrong")).statusCode, 401);
    assert.deepEqual([(await attempt(made.password!)).statusCode, (await attempt(made.password!)).json()], [429, { error: "too_many_attempts" }]);
  } finally {
    await app.close();
    await close();
  }
});

test("the first admin is made once, on an empty database, and only when a provider can sign them in", async () => {
  const { database, close } = await testDatabase();
  try {
    assert.equal(await ensureFirstAdmin(database, "Owner@Example.com", false), false, "no provider: a password-less account would be locked out");
    assert.equal(await ensureFirstAdmin(database, "", true), false);
    assert.equal(await ensureFirstAdmin(database, "Owner@Example.com", true), true);
    const { rows } = await database.query("SELECT email, name, is_admin, password_hash FROM users");
    assert.deepEqual(rows, [{ email: "owner@example.com", name: "owner", is_admin: true, password_hash: null }]);
    assert.equal(await ensureFirstAdmin(database, "other@example.com", true), false, "never a second one");
  } finally {
    await close();
  }
});
