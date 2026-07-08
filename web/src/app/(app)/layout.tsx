import { auth } from "@/auth";
import { TopBar } from "@/components/shell/top-bar";
import { PrivacyConsentModal } from "@/components/shell/privacy-consent-modal";
import { getPrivacyConsentStatus, PRIVACY_POLICY_VERSION } from "@/lib/privacy-consent";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // middleware.ts already redirects unauthenticated requests to /login, so
  // `session` is guaranteed here — this call just reads the name for the shell.
  // middleware.ts가 미인증 요청을 이미 /login으로 보내므로 여기선 session이
  // 보장된다 — 이 호출은 셸에 쓸 이름만 읽는다.
  const [session, consent] = await Promise.all([auth(), getPrivacyConsentStatus()]);

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar userName={session?.user.name ?? ""} />
      <main className="flex-1">{children}</main>
      {!consent.consented && <PrivacyConsentModal version={PRIVACY_POLICY_VERSION} />}
    </div>
  );
}
