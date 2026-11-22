// Signing in through somebody else's login page (Google, Pocket ID), by OpenID Connect.
// It never makes an account: the email the provider vouches for must already belong to
// one an admin made. The first time, the provider's own id for the person is tied to the
// account, and after that the id is what matches, so a later change of email there
// changes nothing here.

import { createHash, createPublicKey, randomBytes, verify, type JsonWebKey } from "node:crypto";
import type { Database } from "./db.js";

export type OidcProvider = {
  /** In addresses and in the table: "google". */
  id: string;
  /** On the button: "Google". */
  name: string;
  issuer: string;
  clientId: string;
  clientSecret: string;
  /** Take the email without the provider's "verified" mark. Only for a provider whose accounts the owner makes. */
  trustEmail?: boolean;
};

export type Fetcher = typeof fetch;
type Discovery = { issuer: string; authorization_endpoint: string; token_endpoint: string; jwks_uri: string };
type Claims = { iss?: string; aud?: string | string[]; exp?: number; nonce?: string; sub?: string; email?: string; email_verified?: boolean };

const HOUR = 3_600_000;
const b64 = (value: Buffer) => value.toString("base64url");

export function createOidc(providers: OidcProvider[], database: Database, options: { fetcher?: Fetcher; now?: () => number } = {}) {
  const fetcher = options.fetcher ?? fetch;
  const now = options.now ?? Date.now;
  const byId = new Map(providers.map((provider) => [provider.id, provider]));
  // What a provider publishes about itself and its signing keys, asked for at most hourly.
  const kept = new Map<string, { at: number; value: unknown }>();

  async function getJson<T>(url: string): Promise<T> {
    const held = kept.get(url);
    if (held && now() - held.at < HOUR) return held.value as T;
    const response = await fetcher(url, { headers: { accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    const value = (await response.json()) as T;
    kept.set(url, { at: now(), value });
    return value;
  }
  const discover = (provider: OidcProvider) => getJson<Discovery>(`${provider.issuer.replace(/\/$/, "")}/.well-known/openid-configuration`);

  /** Checks the signature and that the token was made by this provider, for this app, for this sign-in, and is still good. */
  async function readIdToken(provider: OidcProvider, discovery: Discovery, token: string, nonce: string): Promise<Claims | null> {
    const [head, body, signature] = token.split(".");
    if (!head || !body || !signature) return null;
    const header = JSON.parse(Buffer.from(head, "base64url").toString()) as { alg?: string; kid?: string };
    if (header.alg !== "RS256" && header.alg !== "ES256") return null;
    const find = async () => (await getJson<{ keys: (JsonWebKey & { kid?: string })[] }>(discovery.jwks_uri)).keys.find((key) => key.kid === header.kid);
    let jwk = await find();
    if (!jwk) {
      // The provider may have changed its keys since they were last asked for.
      kept.delete(discovery.jwks_uri);
      jwk = await find();
    }
    if (!jwk) return null;
    const key = createPublicKey({ key: jwk, format: "jwk" });
    const signed = verify("sha256", Buffer.from(`${head}.${body}`), header.alg === "ES256" ? { key, dsaEncoding: "ieee-p1363" } : key, Buffer.from(signature, "base64url"));
    if (!signed) return null;
    const claims = JSON.parse(Buffer.from(body, "base64url").toString()) as Claims;
    const audience = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    if (claims.iss !== discovery.issuer || !audience.includes(provider.clientId) || !claims.exp || claims.exp * 1000 < now() || claims.nonce !== nonce || !claims.sub) return null;
    return claims;
  }

  return {
    list: () => providers.map(({ id, name }) => ({ id, name })),
    has: (id: string) => byId.has(id),

    /** Where to send the browser, and what it must bring back (kept in a cookie meanwhile). */
    async begin(id: string, redirectUri: string): Promise<{ url: string; pending: string }> {
      const provider = byId.get(id)!;
      const discovery = await discover(provider);
      const [state, nonce, verifier] = [b64(randomBytes(16)), b64(randomBytes(16)), b64(randomBytes(32))];
      const url = new URL(discovery.authorization_endpoint);
      url.search = new URLSearchParams({
        response_type: "code",
        client_id: provider.clientId,
        redirect_uri: redirectUri,
        scope: "openid email profile",
        state,
        nonce,
        code_challenge: b64(createHash("sha256").update(verifier).digest()),
        code_challenge_method: "S256",
      }).toString();
      return { url: url.toString(), pending: [id, state, nonce, verifier].join(".") };
    },

    /** The account the returning browser may sign in to, or why not. */
    async finish(id: string, redirectUri: string, query: { code?: string; state?: string }, pending: string | null): Promise<{ userId: string } | { error: "sign_in_failed" | "no_account" }> {
      const provider = byId.get(id)!;
      const [pendingId, state, nonce, verifier] = (pending ?? "").split(".");
      if (!query.code || !state || !nonce || !verifier || pendingId !== id || query.state !== state) return { error: "sign_in_failed" };
      const discovery = await discover(provider);
      const response = await fetcher(discovery.token_endpoint, {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded", accept: "application/json" },
        body: new URLSearchParams({ grant_type: "authorization_code", code: query.code, redirect_uri: redirectUri, client_id: provider.clientId, client_secret: provider.clientSecret, code_verifier: verifier }),
      });
      if (!response.ok) return { error: "sign_in_failed" };
      const { id_token: idToken } = (await response.json()) as { id_token?: string };
      const claims = idToken ? await readIdToken(provider, discovery, idToken, nonce) : null;
      if (!claims) return { error: "sign_in_failed" };

      const known = await database.query("SELECT user_id FROM user_identities WHERE provider = $1 AND subject = $2", [id, claims.sub]);
      if (known.rows[0]) return { userId: String(known.rows[0]["user_id"]) };
      if (!claims.email || !(claims.email_verified === true || provider.trustEmail)) return { error: "no_account" };
      const { rows } = await database.query("SELECT id FROM users WHERE email = $1", [claims.email.trim().toLowerCase()]);
      if (!rows[0]) return { error: "no_account" };
      const userId = String(rows[0]["id"]);
      await database.query("INSERT INTO user_identities (provider, subject, user_id) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING", [id, claims.sub, userId]);
      // A one-time password nobody has used yet is not needed now; a reset gives a new one.
      await database.query("UPDATE users SET password_hash = NULL, must_change = false WHERE id = $1 AND must_change", [userId]);
      return { userId };
    },
  };
}

export type Oidc = ReturnType<typeof createOidc>;

/** The providers set up in the environment. One with no client id is left out. */
export function providersFromEnv(env: NodeJS.ProcessEnv): OidcProvider[] {
  const providers: OidcProvider[] = [];
  if (env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET) providers.push({ id: "google", name: "Google", issuer: "https://accounts.google.com", clientId: env.GOOGLE_CLIENT_ID, clientSecret: env.GOOGLE_CLIENT_SECRET });
  if (env.POCKETID_ISSUER && env.POCKETID_CLIENT_ID && env.POCKETID_CLIENT_SECRET)
    providers.push({ id: "pocketid", name: "Pocket ID", issuer: env.POCKETID_ISSUER, clientId: env.POCKETID_CLIENT_ID, clientSecret: env.POCKETID_CLIENT_SECRET, trustEmail: true });
  return providers;
}
