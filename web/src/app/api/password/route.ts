import { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://api:8000";

// Dedicated route like /api/signup: the API path is /auth/password, but the
// BFF catch-all would map it to /api/auth/password — a path NextAuth's own
// catch-all already owns. So it gets its own proxy at /api/password.
// /api/signup처럼 전용 라우트: API 경로는 /auth/password인데 BFF catch-all을
// 쓰면 /api/auth/password가 되고, 그 경로는 NextAuth 자체 catch-all이 이미
// 점유한다. 그래서 /api/password에 전용 프록시를 둔다.
export async function PATCH(request: NextRequest) {
  const token = await getToken({ req: request, secret: process.env.AUTH_SECRET });
  if (!token) {
    return Response.json(
      { error: { code: "unauthenticated", message: "로그인이 필요합니다." } },
      { status: 401 },
    );
  }

  const upstream = await fetch(`${API_BASE_URL}/auth/password`, {
    method: "PATCH",
    headers: {
      "content-type": request.headers.get("content-type") ?? "application/json",
      // Same pnpm/@auth-core hoisting gap as the BFF route — see its comment.
      Authorization: `Bearer ${token.accessToken as string}`,
    },
    body: request.body,
    duplex: "half",
  } as RequestInit);

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);

  return new Response(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
