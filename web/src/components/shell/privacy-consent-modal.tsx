"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function PrivacyConsentModal({ version }: { version: string }) {
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleAgree() {
    startTransition(async () => {
      const res = await fetch("/api/privacy-consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version }),
      });
      if (!res.ok) {
        setError("동의 처리에 실패했습니다. 다시 시도해 주세요.");
        return;
      }
      // Server layout re-runs getPrivacyConsentStatus() and stops rendering
      // this modal once it sees the new consent row.
      // 서버 레이아웃이 getPrivacyConsentStatus()를 재실행해 동의 반영을
      // 확인하면 이 모달을 더 이상 렌더링하지 않는다.
      router.refresh();
    });
  }

  return (
    <Dialog open>
      <DialogContent
        showCloseButton={false}
        onInteractOutside={(event) => event.preventDefault()}
        onEscapeKeyDown={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>개인정보 처리 안내</DialogTitle>
          <DialogDescription>
            다정 AI는 대화 내용을 저장하고, 매주 개인 맞춤 메모리를 생성하는 데 활용합니다. 서비스
            이용을 시작하려면 아래 내용에 동의해 주세요.
          </DialogDescription>
        </DialogHeader>
        <label className="flex items-start gap-2 text-body-sm text-ink">
          <Checkbox
            checked={agreed}
            onCheckedChange={(checked) => setAgreed(checked === true)}
          />
          위 내용에 동의합니다.
        </label>
        {error && (
          <p role="alert" className="text-body-sm text-semantic-error">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button variant="secondary" onClick={() => void signOut({ redirectTo: "/login" })}>
            취소
          </Button>
          <Button disabled={!agreed || isPending} onClick={handleAgree}>
            동의 후 시작
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
