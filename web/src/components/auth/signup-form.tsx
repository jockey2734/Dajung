"use client";

import { useState, useTransition, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// serving-plan §3 error codes for /auth/signup.
const ERROR_MESSAGES: Record<string, string> = {
  invalid_code: "유효하지 않은 통과번호입니다.",
  email_exists: "이미 가입된 이메일입니다.",
};
const DEFAULT_ERROR_MESSAGE = "가입에 실패했습니다. 입력값을 확인해 주세요.";

interface ApiErrorBody {
  error?: { code: string; message: string };
}

export function SignupForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [invitationCode, setInvitationCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    startTransition(async () => {
      const res = await fetch("/api/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          name,
          invitation_code: invitationCode,
        }),
      });

      if (!res.ok) {
        // FastAPI's own pydantic validation errors (422) don't use the
        // ApiError envelope, so `error?.code` may legitimately be absent.
        // FastAPI 자체 pydantic 검증 에러(422)는 ApiError 포맷이 아니라서
        // `error?.code`가 없을 수 있다.
        const body = (await res.json().catch(() => null)) as ApiErrorBody | null;
        const code = body?.error?.code;
        setError((code && ERROR_MESSAGES[code]) ?? DEFAULT_ERROR_MESSAGE);
        return;
      }

      setSuccess(true);
    });
  }

  if (success) {
    return (
      <div className="flex w-full max-w-sm flex-col items-center gap-4 text-center">
        <p className="text-body text-ink">가입이 완료되었습니다. 로그인해 주세요.</p>
        <Button asChild>
          <Link href="/login">로그인하러 가기</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="name">이름</Label>
        <Input id="name" required value={name} onChange={(event) => setName(event.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">이메일</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">비밀번호</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={72}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="invitation-code">통과번호</Label>
        <Input
          id="invitation-code"
          required
          value={invitationCode}
          onChange={(event) => setInvitationCode(event.target.value)}
        />
      </div>
      {error && (
        <p role="alert" className="text-body-sm text-semantic-error">
          {error}
        </p>
      )}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={isPending}>
          가입
        </Button>
        <Link href="/login" className="text-body-sm-medium text-link">
          로그인으로 돌아가기
        </Link>
      </div>
    </form>
  );
}
