"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// serving-plan §3 error codes for /auth/signin, rendered verbatim in Korean.
// /auth/signin의 serving-plan §3 에러 코드 — 한국어 메시지 그대로 렌더링.
const ERROR_MESSAGES: Record<string, string> = {
  bad_credentials: "이메일 또는 비밀번호가 올바르지 않습니다.",
  locked_out: "로그인 시도가 너무 많습니다. 1시간 후 다시 시도해 주세요.",
  validation: "이메일과 비밀번호를 입력해 주세요.",
};
const DEFAULT_ERROR_MESSAGE = "로그인에 실패했습니다. 다시 시도해 주세요.";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    startTransition(async () => {
      const result = await signIn("credentials", { email, password, redirect: false });
      if (result?.error) {
        setError((result.code && ERROR_MESSAGES[result.code]) ?? DEFAULT_ERROR_MESSAGE);
        return;
      }
      router.push(searchParams.get("callbackUrl") ?? "/chat");
      router.refresh();
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-4">
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
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      {error && (
        <p role="alert" className="text-body-sm text-semantic-error">
          {error}
        </p>
      )}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={isPending}>
          로그인
        </Button>
        <Link href="/signup" className="text-body-sm-medium text-link">
          가입 (통과번호)
        </Link>
      </div>
    </form>
  );
}
