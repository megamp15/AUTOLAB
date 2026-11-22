import assert from "node:assert/strict";
import { createSign, generateKeyPairSync } from "node:crypto";
import test from "node:test";
import { createApp } from "../src/server/app.js";
import { createUser } from "../src/server/auth.js";
import { providersFromEnv, type Fetcher } from "../src/server/oidc.js";
import { testDatabase } from "./helpers.js";

const ISSUER = "https://login.example";
const provider = { id: "google", name: "Google", issuer: ISSUER, clientId: "client-1", clientSecret: "secret-1" };

/** A stand-in login provider: it signs an id token for whoever `next` says is at the keyboard. */
function fakeProvider() {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const state = { next: { sub: "g-1", email: "friend@example.com", email_verified: true } as Record<string, unknown>, nonce: "", aud: "client-1", tokenCalls: [] as URLSearchParams[] };
  const part = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const fetcher = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    const reply = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
    if (url === `${ISSUER}/.well-known/openid-configuration`) return reply({ issuer: ISSUER, authorization_endpoint: `${ISSUER}/authorize`, token_endpoint: `${ISSUER}/token`, jwks_uri: `${ISSUER}/keys` });
    if (url === `${ISSUER}/keys`) return reply({ keys: [{ ...publicKey.export({ format: "jwk" }), kid: "k1" }] });
    if (url === `${ISSUER}/token`) {
      state.tokenCalls.push(new URLSearchParams(String(init?.body)));
      const signed = `${part({ alg: "RS256", kid: "k1" })}.${part({ iss: ISSUER, aud: state.aud, exp: Math.floor(Date.now() / 1000) + 300, nonce: state.nonce, ...state.next })}`;
      return reply({ id_token: `${signed}.${createSign("sha256").update(signed).sign(privateKey).toString("base64url")}` });
    }
    return new Response("{}", { status: 404 });
  }) as Fetcher;
  return { state, fetcher };
}

test("a provider signs in only the people an admin has added, and never makes an account", async () => {
  const { database, close } = await testDatabase();
  const fake = fakeProvider();
  const app = createApp({ database, providers: [provider], publicUrls: ["https://__app__.example"], fetcher: fake.fetcher }, { logger: false });
  /** Leaves for the provider and comes back, as a browser would. `tamper` changes what comes back. */
  const signIn = async (tamper: { state?: string } = {}) => {
    const out = await app.inject({ method: "GET", url: "/api/auth/oidc/google" });
    assert.equal(out.statusCode, 302);
    const to = new URL(String(out.headers.location));
    assert.equal(to.origin + to.pathname, `${ISSUER}/authorize`);
    assert.equal(to.searchParams.get("redirect_uri"), "https://__app__.example/api/auth/oidc/google/callback");
    assert.equal(to.searchParams.get("code_challenge_method"), "S256");
    fake.state.nonce = to.searchParams.get("nonce")!;
    const pending = String(out.headers["set-cookie"]).split(";")[0]!;
    assert.match(String(out.headers["set-cookie"]), /^__app___signin=.+; Path=\/api\/auth\/oidc; HttpOnly; SameSite=Lax; Max-Age=600$/);
    return app.inject({ method: "GET", url: `/api/auth/oidc/google/callback?code=abc&state=${tamper.state ?? to.searchParams.get("state")}`, headers: { cookie: pending } });
  };
  const sessionOf = (response: { headers: Record<string, unknown> }) => (response.headers["set-cookie"] as string[]).find((cookie) => cookie.startsWith("__app___session="))!.split(";")[0]!;
  const count = async (table: string) => Number((await database.query(`SELECT count(*) FROM ${table}`)).rows[0]!["count"]);
  try {
    assert.deepEqual((await app.inject({ method: "GET", url: "/api/auth/providers" })).json(), { providers: [{ id: "google", name: "Google" }] });
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/oidc/facebook" })).statusCode, 404);

    // Nobody has been added: a real Google account gets nothing, and no account appears.
    assert.equal((await signIn()).headers.location, "/?signin=no_account");
    assert.equal(await count("users"), 0);

    // Added without a password: Google is the way in.
    const friend = (await createUser(database, { email: "Friend@Example.com", name: "Friend", password: false }))!;
    assert.deepEqual([friend.password, friend.user.mustChange], [null, false]);
    const password = await app.inject({ method: "POST", url: "/api/auth/login", headers: { "content-type": "application/json" }, payload: { email: "friend@example.com", password: "" } });
    assert.equal(password.statusCode, 401, "an account with no password cannot be signed in to with one");

    const back = await signIn();
    assert.equal(back.headers.location, "/");
    assert.equal(fake.state.tokenCalls.at(-1)!.get("client_secret"), "secret-1");
    assert.ok(fake.state.tokenCalls.at(-1)!.get("code_verifier"));
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie: sessionOf(back) } })).json().user.email, "friend@example.com");

    // An answer that does not belong to the sign-in this browser started is refused.
    assert.equal((await signIn({ state: "someone-elses" })).headers.location, "/?signin=sign_in_failed");
    fake.state.aud = "another-app";
    assert.equal((await signIn()).headers.location, "/?signin=sign_in_failed", "a token made for another app");
    fake.state.aud = "client-1";

    // An unverified email proves nothing, so it matches no account.
    fake.state.next = { sub: "g-2", email: "friend@example.com", email_verified: false };
    assert.equal((await signIn()).headers.location, "/?signin=no_account");

    // Once tied, the provider's id is what matches: a changed email there still signs in here.
    fake.state.next = { sub: "g-1", email: "renamed@example.com", email_verified: true };
    assert.equal((await signIn()).headers.location, "/");
    assert.deepEqual([await count("users"), await count("user_identities")], [1, 1]);

    // Someone given a one-time password who signs in with Google instead skips choosing one.
    const other = (await createUser(database, { email: "other@example.com", name: "Other" }))!;
    fake.state.next = { sub: "g-3", email: "other@example.com", email_verified: true };
    const otherBack = await signIn();
    assert.equal((await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie: sessionOf(otherBack) } })).json().user.mustChange, false);
    const stale = await app.inject({ method: "POST", url: "/api/auth/login", headers: { "content-type": "application/json" }, payload: { email: "other@example.com", password: other.password } });
    assert.equal(stale.statusCode, 401, "the unused one-time password no longer works");
  } finally {
    await app.close();
    await close();
  }
});

test("providers come from the environment, and one without its settings is left out", () => {
  assert.deepEqual(providersFromEnv({}), []);
  assert.deepEqual(providersFromEnv({ GOOGLE_CLIENT_ID: "a" }), []);
  const both = providersFromEnv({ GOOGLE_CLIENT_ID: "a", GOOGLE_CLIENT_SECRET: "b", POCKETID_ISSUER: "https://auth.example", POCKETID_CLIENT_ID: "c", POCKETID_CLIENT_SECRET: "d" });
  assert.deepEqual(both.map((provider) => [provider.id, provider.issuer, provider.trustEmail ?? false]), [["google", "https://accounts.google.com", false], ["pocketid", "https://auth.example", true]]);
});
