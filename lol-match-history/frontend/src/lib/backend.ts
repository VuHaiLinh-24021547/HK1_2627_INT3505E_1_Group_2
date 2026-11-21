import "server-only";

const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
const CLIENT_ID = process.env.OAUTH_CLIENT_ID || "demo-client";
const CLIENT_SECRET = process.env.OAUTH_CLIENT_SECRET || "demo-secret";

let cachedToken: { token: string; expiresAt: number } | null = null;

async function getAccessToken(forceRefresh = false): Promise<string> {
  const now = Date.now();
  if (!forceRefresh && cachedToken && cachedToken.expiresAt - now > 30_000) {
    return cachedToken.token;
  }
  const resp = await fetch(`${BACKEND_URL}/api/v1/oauth/tokens`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grant_type: "client_credentials",
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
    }),
    cache: "no-store",
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Failed to obtain backend OAuth token (${resp.status}): ${text}`);
  }
  const data = (await resp.json()) as { access_token: string; expires_in: number };
  cachedToken = {
    token: data.access_token,
    expiresAt: now + (data.expires_in || 900) * 1000,
  };
  return cachedToken.token;
}

export async function backendFetch(
  apiPath: string,
  init: RequestInit = {},
  { auth = true }: { auth?: boolean } = {}
): Promise<Response> {
  const url = `${BACKEND_URL}/api/v1/${apiPath.replace(/^\/+/, "")}`;

  const run = async (forceRefresh: boolean) => {
    const headers = new Headers(init.headers);
    if (auth) {
      const token = await getAccessToken(forceRefresh);
      headers.set("Authorization", `Bearer ${token}`);
    }
    return fetch(url, { ...init, headers, cache: "no-store" });
  };

  let resp = await run(false);
  if (auth && resp.status === 401) {
    resp = await run(true);
  }
  return resp;
}

export async function backendJson<T>(
  apiPath: string,
  init: RequestInit = {},
  opts?: { auth?: boolean }
): Promise<{ ok: true; status: number; data: T } | { ok: false; status: number; error: unknown }> {
  const resp = await backendFetch(apiPath, init, opts);
  const text = await resp.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = { detail: text };
  }
  if (!resp.ok) {
    return { ok: false, status: resp.status, error: parsed };
  }
  return { ok: true, status: resp.status, data: parsed as T };
}
