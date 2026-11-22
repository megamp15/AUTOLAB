// Calls to the server. The session is a cookie the browser sends by itself.

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
  }
}

export async function api<T>(method: "GET" | "POST" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    ...(body !== undefined ? { headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const reply = (await response.json().catch(() => ({}))) as { error?: string; detail?: string };
    throw new ApiError(response.status, reply.error ?? "failed", reply.detail ?? reply.error ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}
