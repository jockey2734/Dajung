import { PasswordChangeForm } from "@/components/auth/password-change-form";

// Deliberately outside the (app) route group: the (app) layout redirects
// here whenever me.must_change_password is true, so this page must not
// share that layout or the redirect would loop. No shell either — the
// forced flow allows nothing but changing the password (webapp-spec S20).
// 의도적으로 (app) 라우트 그룹 밖에 둔다: me.must_change_password가 true면
// (app) 레이아웃이 여기로 리다이렉트하므로, 이 페이지가 그 레이아웃을 공유하면
// 무한 루프가 된다. 셸도 없다 — 강제 플로우에서는 비밀번호 변경 외에 아무
// 것도 허용하지 않는다 (webapp-spec S20).
export default function PasswordPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-cream px-6">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-heading-2 font-semibold text-ink">비밀번호 변경</h1>
        <p className="text-body-sm text-taupe">
          임시 비밀번호로 로그인했습니다. 계속하려면 새 비밀번호를 설정해 주세요.
        </p>
      </div>
      <PasswordChangeForm />
    </div>
  );
}
