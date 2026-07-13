import type { DefaultSession } from "next-auth";

// "president" joined the role set in S18. The session claim is only a
// snapshot from sign-in time — anything privilege-related must re-check
// /auth/me (see server-me.ts), so this union is for typing, not authz.
// S18에서 역할 집합에 "president"가 추가됐다. 세션 claim은 로그인 시점
// 스냅샷일 뿐 — 권한 판단은 /auth/me 재조회(server-me.ts)로 하므로 이
// 유니온은 타입용이지 인가용이 아니다.
declare module "next-auth" {
  interface User {
    role: "owner" | "president" | "staff";
    accessToken: string;
  }

  interface Session {
    user: {
      id: string;
      role: "owner" | "president" | "staff";
    } & DefaultSession["user"];
  }
}
