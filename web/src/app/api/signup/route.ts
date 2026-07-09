import { NextRequest } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://api:8000";

// The only unauthenticated BFF passthrough — there's no Auth.js provider for
// signup (Credentials only covers signin), and it can't live under
// `/api/auth/*` since NextAuth's own catch-all already owns that path.
// 유일한 미인증 BFF 통로 — Credentials는 signin만 다루므로 signup용 Auth.js
// 프로바이더가 없고, `/api/auth/*`는 이미 NextAuth 자체 catch-all이 점유해
// 그 아래 둘 수 없다.
export async function POST(request: NextRequest) {
  const upstream = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "content-type": request.headers.get("content-type") ?? "application/json" },
    body: request.body,
    duplex: "half",
  } as RequestInit);

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}
