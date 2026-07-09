import { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://api:8000";

// Only these are safe to forward as-is. Never forward the incoming `cookie`
// header (Auth.js session cookie has no business reaching FastAPI), and never
// forward upstream `content-encoding`/`content-length` back to the client —
// undici already decoded the body, so those would describe bytes that no
// longer match the re-streamed response.
// 이 헤더들만 그대로 전달해도 안전하다. 들어오는 `cookie`(Auth.js 세션 쿠키)는
// FastAPI로 보낼 이유가 없고, 업스트림 `content-encoding`/`content-length`를
// 그대로 돌려주면 undici가 이미 압축을 푼 바디와 길이가 안 맞게 된다.
const REQUEST_HEADERS_TO_FORWARD = ["content-type", "accept"];

type RouteParams = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, params: Promise<{ path: string[] }>): Promise<Response> {
  const token = await getToken({ req: request, secret: process.env.AUTH_SECRET });
  if (!token) {
    // Signal for the client: no Auth.js session at all — distinct from a
    // FastAPI-issued 401 (token_expired/token_invalid), which we pass through
    // verbatim below since the browser should show that message, not this one.
    // 클라이언트용 신호: Auth.js 세션 자체가 없는 경우 — 아래에서 그대로 전달하는
    // FastAPI발 401(token_expired/token_invalid)과는 다르다. 그 경우는 API
    // 메시지를 그대로 보여줘야 하므로 여기서 가로채지 않는다.
    return Response.json(
      { error: { code: "unauthenticated", message: "로그인이 필요합니다." } },
      { status: 401 },
    );
  }

  const { path } = await params;
  const target = new URL(`/${path.join("/")}${request.nextUrl.search}`, API_BASE_URL);

  const headers = new Headers();
  for (const name of REQUEST_HEADERS_TO_FORWARD) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  // See auth.ts's session-callback comment — same pnpm/@auth-core hoisting
  // gap means `token.accessToken` reads back as `unknown` here too.
  headers.set("Authorization", `Bearer ${token.accessToken as string}`);

  const hasRequestBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: hasRequestBody ? request.body : undefined,
    // Node's fetch requires this when streaming a request body.
    // Node fetch는 요청 바디를 스트림으로 보낼 때 이 옵션을 요구한다.
    ...(hasRequestBody ? { duplex: "half" } : {}),
  } as RequestInit);

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);

  // SSE and everything else both just pipe the upstream body stream straight
  // through — no buffering, so `/chat/stream` tokens reach the browser as
  // FastAPI emits them.
  // SSE든 아니든 업스트림 바디 스트림을 그대로 흘려보낸다 — 버퍼링 없이,
  // FastAPI가 내보내는 그대로 `/chat/stream` 토큰이 브라우저에 도달한다.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  return proxy(request, params);
}
export async function POST(request: NextRequest, { params }: RouteParams) {
  return proxy(request, params);
}
export async function PATCH(request: NextRequest, { params }: RouteParams) {
  return proxy(request, params);
}
export async function PUT(request: NextRequest, { params }: RouteParams) {
  return proxy(request, params);
}
export async function DELETE(request: NextRequest, { params }: RouteParams) {
  return proxy(request, params);
}
