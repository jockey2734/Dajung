import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { TopBar } from "@/components/shell/top-bar";
import { PrivacyConsentModal } from "@/components/shell/privacy-consent-modal";
import { ToastProvider } from "@/components/shell/toast-provider";
import { resolveAppGate } from "@/lib/admin-access";
import { getPrivacyConsentStatus, PRIVACY_POLICY_VERSION } from "@/lib/privacy-consent";
import { getMe } from "@/lib/server-me";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // middleware.ts already redirects unauthenticated requests to /login, so
  // `session` is guaranteed here — this call just reads the name for the shell.
  // middleware.ts가 미인증 요청을 이미 /login으로 보내므로 여기선 session이
  // 보장된다 — 이 호출은 셸에 쓸 이름만 읽는다.
  const [session, consent, me] = await Promise.all([
    auth(),
    getPrivacyConsentStatus(),
    getMe(),
  ]);

  // Forced password change (webapp-spec S20): after an admin reset, no (app)
  // screen renders until the password is changed — /password lives outside
  // this layout, so the redirect can't loop.
  // 강제 비번 변경 (webapp-spec S20): 관리자 재설정 후에는 비밀번호를 바꾸기
  // 전까지 어떤 (app) 화면도 렌더되지 않는다 — /password는 이 레이아웃 밖이라
  // 리다이렉트가 루프하지 않는다.
  const gate = resolveAppGate(me);
  if (gate) redirect(gate);

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar userName={session?.user.name ?? ""} role={me?.role ?? null} />
      <main className="flex-1">{children}</main>
      {!consent.consented && <PrivacyConsentModal version={PRIVACY_POLICY_VERSION} />}
      <ToastProvider />
    </div>
  );
}
