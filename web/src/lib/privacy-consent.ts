import { getAccessToken } from "@/lib/server-token";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://api:8000";

// webapp-spec S1.5 — a code constant on the API side too (bump on policy
// text changes, not a config knob).
// webapp-spec S1.5 — API 쪽도 코드 상수(문안 개정 시 상수를 바꾼다, config 아님).
export const PRIVACY_POLICY_VERSION = "2026-07-08";

interface PrivacyConsentStatus {
  consented: boolean;
  version: string | null;
}

export async function getPrivacyConsentStatus(): Promise<PrivacyConsentStatus> {
  const token = await getAccessToken();
  // middleware.ts already redirects unauthenticated requests away from every
  // page that renders this — reaching here without a token shouldn't happen.
  if (!token) return { consented: true, version: null };

  try {
    const res = await fetch(`${API_BASE_URL}/privacy-consent`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return { consented: true, version: null };
    return (await res.json()) as PrivacyConsentStatus;
  } catch {
    // Fail-open: a transient API hiccup shouldn't lock ~8 known users out of
    // the whole app over a one-time consent screen. Worth a second opinion —
    // flagged as a spec deviation in the PR rather than assumed correct.
    // 실패 시 열어준다: 일회성 동의 화면 때문에 API 일시 장애로 전원이 앱
    // 전체에서 막히는 건 과하다. 확신 없는 판단이라 PR에 이탈로 기록.
    return { consented: true, version: null };
  }
}
