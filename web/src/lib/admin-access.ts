import type { Role } from "@/types/admin";

// Admin entry rule (webapp-spec S20): decided from the /auth/me *live* value,
// never from the Auth.js session claim — a just-demoted president's cookie
// still says "president" until re-login, but the DB row is already staff.
// 관리자 진입 규칙 (webapp-spec S20): Auth.js 세션 claim이 아니라 /auth/me
// 실값으로 판정 — 방금 강등된 회장의 쿠키는 재로그인 전까지 "president"지만
// DB 행은 이미 staff다.
export function canAccessAdmin(role: Role): boolean {
  return role === "owner" || role === "president";
}

export interface MeGate {
  role: Role;
  must_change_password: boolean;
}

// Where the (app) layout must send the user before rendering anything else.
// (app) 레이아웃이 다른 화면을 렌더하기 전에 보낼 곳.
export function resolveAppGate(me: MeGate | null): "/password" | null {
  if (me?.must_change_password) return "/password";
  return null;
}
