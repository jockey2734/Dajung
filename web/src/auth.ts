import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { credentialsSignin } from "@/lib/credentials-signin";

// Six months, matching the FastAPI JWT's absolute expiry (SECURITY.md §3).
// FastAPI JWT의 6개월 절대 만료와 맞춘다 (SECURITY.md §3).
const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 180;

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  session: {
    strategy: "jwt",
    maxAge: SESSION_MAX_AGE_SECONDS,
  },
  pages: {
    signIn: "/login",
  },
  providers: [
    Credentials({
      credentials: {
        email: {},
        password: {},
      },
      authorize(credentials) {
        return credentialsSignin(credentials?.email, credentials?.password);
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // `user` is only present on the initial sign-in call — persist the
      // fields we need into the encrypted JWT cookie from there on.
      // `user`는 최초 로그인 호출에만 존재 — 이후엔 암호화된 JWT 쿠키에 보존된 값을 쓴다.
      if (user) {
        token.accessToken = user.accessToken;
        token.role = user.role;
        token.id = user.id ?? token.id;
      }
      return token;
    },
    async session({ session, token }) {
      // Client-visible session: user only. accessToken never leaves the
      // server (S3 spec — read it server-side via `auth()` in the BFF route).
      // 클라이언트 세션엔 user만 노출. accessToken은 서버 밖으로 나가지 않는다
      // (S3 명세 — BFF 라우트에서 `auth()`로 서버 측에서만 읽는다).
      // `next-auth/jwt`'s JWT type is re-exported via `export *` from @auth/core,
      // which pnpm doesn't hoist as a resolvable package — declaration-merging
      // augmentation silently fails to attach, so `token.id`/`token.role` stay
      // `unknown` (JWT's own index signature). Narrow explicitly instead.
      // next-auth/jwt의 JWT 타입은 @auth/core에서 `export *`로 재노출되는데,
      // pnpm이 이를 hoist하지 않아 선언 병합이 붙지 않는다 — token.id/token.role이
      // JWT 자체 인덱스 시그니처로 인해 unknown으로 남는다. 명시적으로 좁혀 쓴다.
      session.user.id = token.id as string;
      session.user.role = token.role as "owner" | "president" | "staff";
      return session;
    },
    // Drives middleware.ts: unauthenticated requests to the (app) route
    // group get redirected to `pages.signIn` automatically.
    // middleware.ts를 구동 — 미인증 요청은 (app) 라우트 그룹에서
    // `pages.signIn`으로 자동 리다이렉트된다.
    authorized({ auth: session }) {
      return Boolean(session);
    },
  },
});
