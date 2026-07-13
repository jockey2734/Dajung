import { getAccessToken } from "@/lib/server-token";
import type { Role } from "@/types/admin";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://api:8000";

// Mirrors api/app/schemas/auth.py UserOut.
// api/app/schemas/auth.py UserOut을 반영.
export interface Me {
  id: string;
  email: string;
  name: string;
  role: Role;
  must_change_password: boolean;
}

// Live per-request identity for server components (webapp-spec S20): the
// admin button/guard and the forced-password gate all key off the DB row,
// not the Auth.js cookie — a demotion or a password reset must take effect
// on the very next request, without re-login.
// 서버 컴포넌트용 요청 단위 실시간 신원 (webapp-spec S20): 관리자 버튼·가드와
// 강제 비번 변경 게이트는 Auth.js 쿠키가 아니라 DB 행을 기준으로 한다 —
// 강등이나 비번 재설정은 재로그인 없이 바로 다음 요청부터 반영돼야 한다.
export async function getMe(): Promise<Me | null> {
  const token = await getAccessToken();
  if (!token) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Me;
  } catch {
    // Fail closed for privileges: no admin button, no admin page. The rest
    // of the app still renders (same availability reasoning as
    // privacy-consent.ts, but privileges must never fail open).
    // 권한은 닫는 쪽으로 실패: 관리자 버튼·페이지 미노출. 나머지 앱은 그대로
    // 렌더된다(privacy-consent.ts와 같은 가용성 논리, 단 권한은 절대
    // fail-open 금지).
    return null;
  }
}
