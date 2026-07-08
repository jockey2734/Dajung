import { Suspense } from "react";
import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col bg-cream px-6 py-10">
      <div aria-hidden className="text-heading-3">
        🍵
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-8">
        <h1 className="text-display text-ink">Dajung AI</h1>
        <Suspense>
          <LoginForm />
        </Suspense>
      </div>

      <footer className="text-right text-micro text-taupe">
        <p>©2026 임운하 및 다정 운영진. All rights reserved.</p>
        <p>
          본 사이트에서 제공되는 AI 서비스, 코드, 데이터, 문서 등 모든 콘텐츠는 다정 운영진의
          학습·연구 목적에 한해 이용할 수 있습니다.
        </p>
        <p>저작권자의 사전 서면 동의 없이 제3자의 사용, 복제, 수정, 배포 및 상업적 이용을 금지합니다.</p>
        <p>다정 정식 등록 구성원이 아닌 자의 이용은 일절 허용되지 않습니다.</p>
        <p>문의: 임운하 +82 10-9787-0867</p>
      </footer>
    </div>
  );
}
