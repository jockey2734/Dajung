import { redirect } from "next/navigation";
import { AdminShell } from "@/components/admin/admin-shell";
import { canAccessAdmin } from "@/lib/admin-access";
import { getMe } from "@/lib/server-me";

// Server-side gate on the live /auth/me value (webapp-spec S20) — the
// Auth.js cookie's role claim can be stale after a transfer, so it is never
// consulted here. Staff (and any fetch failure) bounce to /chat.
// /auth/me 실값 기준 서버 측 가드 (webapp-spec S20) — Auth.js 쿠키의 role
// claim은 이양 후 낡을 수 있어 여기서 절대 참조하지 않는다. staff(및 조회
// 실패)는 /chat으로 돌려보낸다.
export default async function AdminPage() {
  const me = await getMe();
  if (!me || !canAccessAdmin(me.role)) redirect("/chat");

  return <AdminShell viewerId={me.id} viewerRole={me.role} />;
}
