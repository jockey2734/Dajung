"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { flashToast } from "@/components/shell/toast-provider";

const GENERIC_ERROR = "요청을 처리하지 못했습니다.";

export class AdminApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

// Central escape hatches shared by every admin hook (webapp-spec S20): 403
// means the viewer just lost admin (the post-transfer case) — leave with a
// toast; account_expired means the API now rejects every call — back to
// login with the message. Everything else surfaces as AdminApiError for the
// calling dialog to render inline.
// 모든 admin 훅이 공유하는 중앙 이탈 처리 (webapp-spec S20): 403은 방금
// 관리자 권한을 잃은 경우(이양 직후) — 토스트와 함께 이탈. account_expired는
// 이제 모든 호출이 거부되는 상태 — 메시지와 함께 로그인 화면으로. 그 외는
// 호출한 다이얼로그가 인라인 렌더하도록 AdminApiError로 던진다.
export function useAdminEscalate(): (response: Response) => Promise<never> {
  const router = useRouter();

  return useCallback(
    async (response: Response): Promise<never> => {
      const body = (await response.json().catch(() => null)) as {
        error?: { code?: string; message?: string };
      } | null;
      const code = body?.error?.code ?? "unknown";
      if (response.status === 403) {
        flashToast("권한이 없습니다.");
        router.push("/chat");
      } else if (response.status === 401 && code === "account_expired") {
        await signOut({ callbackUrl: "/login?error=account_expired" });
      }
      throw new AdminApiError(code, body?.error?.message ?? GENERIC_ERROR);
    },
    [router],
  );
}
