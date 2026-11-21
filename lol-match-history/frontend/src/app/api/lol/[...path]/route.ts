import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

const FORWARD_RESPONSE_HEADERS = [
  "content-type",
  "retry-after",
  "location",
  "cache-control",
  "etag",
  "idempotent-replayed",
  "x-trace-id",
];

async function proxy(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const subPath = path.map((seg) => encodeURIComponent(seg)).join("/");
  const search = request.nextUrl.search;
  const target = `${subPath}${search}`;

  const headers: Record<string, string> = {};
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  const idemKey = request.headers.get("idempotency-key");
  if (idemKey) headers["Idempotency-Key"] = idemKey;

  const init: RequestInit = {
    method: request.method,
    headers,
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  try {
    const upstream = await backendFetch(target, init, { auth: subPath !== "health" });
    const body = await upstream.text();
    const respHeaders = new Headers();
    for (const name of FORWARD_RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) respHeaders.set(name, value);
    }
    return new NextResponse(body, { status: upstream.status, headers: respHeaders });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Backend unavailable";
    return NextResponse.json(
      {
        status: 502,
        code: "BACKEND_UNREACHABLE",
        detail: `Không thể kết nối tới Flask backend: ${message}`,
      },
      { status: 502, headers: { "Content-Type": "application/problem+json" } }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
