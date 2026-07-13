"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// serving-plan §3 codes for PATCH /auth/password, rendered verbatim.
// PATCH /auth/password의 serving-plan §3 에러 코드 — 메시지 그대로 렌더링.
const ERROR_MESSAGES: Record<string, string> = {
  bad_credentials: "현재 비밀번호가 올바르지 않습니다.",
  validation: "새 비밀번호는 8자 이상이어야 합니다.",
};
const DEFAULT_ERROR_MESSAGE = "비밀번호 변경에 실패했습니다. 다시 시도해 주세요.";
const MISMATCH_MESSAGE = "새 비밀번호가 서로 일치하지 않습니다.";

export function PasswordChangeForm() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError(MISMATCH_MESSAGE);
      return;
    }
    startTransition(async () => {
      const res = await fetch("/api/password", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          error?: { code?: string };
        } | null;
        setError(
          (body?.error?.code && ERROR_MESSAGES[body.error.code]) ?? DEFAULT_ERROR_MESSAGE,
        );
        return;
      }
      // must_change_password is now false server-side — the (app) layout
      // gate will let the next navigation through.
      // 서버에서 must_change_password가 해제됐다 — (app) 레이아웃 게이트가
      // 다음 이동을 통과시킨다.
      router.push("/chat");
      router.refresh();
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="current-password">현재 비밀번호</Label>
        <Input
          id="current-password"
          type="password"
          autoComplete="current-password"
          required
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="new-password">새 비밀번호 (8자 이상)</Label>
        <Input
          id="new-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="confirm-password">새 비밀번호 확인</Label>
        <Input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
      </div>
      {error && (
        <p role="alert" className="text-body-sm text-semantic-error">
          {error}
        </p>
      )}
      <Button type="submit" disabled={isPending}>
        {isPending ? "변경 중..." : "비밀번호 변경"}
      </Button>
    </form>
  );
}
