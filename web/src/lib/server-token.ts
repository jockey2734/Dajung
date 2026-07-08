import { headers } from "next/headers";
import { getToken } from "next-auth/jwt";

// For Server Components, which have no NextRequest to hand to getToken() —
// only the BFF route (app/api/[...path]/route.ts) has that, and reads the
// token directly from it instead of using this helper.
// Server Component용 — getToken()에 넘길 NextRequest가 없다(BFF 라우트만
// 그걸 갖고 있어 이 헬퍼 없이 직접 읽는다).
export async function getAccessToken(): Promise<string | null> {
  const token = await getToken({
    req: { headers: await headers() },
    secret: process.env.AUTH_SECRET,
  });
  // Same pnpm/@auth-core hoisting gap as auth.ts/route.ts — see those comments.
  return token ? (token.accessToken as string) : null;
}
