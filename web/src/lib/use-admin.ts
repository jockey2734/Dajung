"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { flashToast } from "@/components/shell/toast-provider";
import type {
  AdminUserOut,
  PresidentTransferOut,
  PresidentUserOut,
  TemporaryPasswordOut,
} from "@/types/admin";

const GENERIC_ERROR = "요청을 처리하지 못했습니다.";

class AdminApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export function useAdmin() {
  const router = useRouter();
  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [president, setPresident] = useState<PresidentUserOut | null>(null);
  const [transfers, setTransfers] = useState<PresidentTransferOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Central escape hatches (webapp-spec S20): 403 means the viewer just lost
  // admin (the post-transfer case) — leave with a toast; account_expired
  // means the API now rejects every call — back to login with the message.
  // 중앙 이탈 처리 (webapp-spec S20): 403은 방금 관리자 권한을 잃은 경우
  // (이양 직후 케이스) — 토스트와 함께 이탈. account_expired는 이제 모든
  // 호출이 거부되는 상태 — 메시지와 함께 로그인 화면으로.
  const escalate = useCallback(
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

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const [usersRes, presidentRes, transfersRes] = await Promise.all([
        fetch("/api/admin/users"),
        fetch("/api/admin/president"),
        fetch("/api/admin/president/transfers"),
      ]);
      for (const res of [usersRes, presidentRes, transfersRes]) {
        if (!res.ok) await escalate(res);
      }
      setUsers((await usersRes.json()) as AdminUserOut[]);
      setPresident((await presidentRes.json()) as PresidentUserOut | null);
      setTransfers((await transfersRes.json()) as PresidentTransferOut[]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : GENERIC_ERROR);
    } finally {
      setLoading(false);
    }
  }, [escalate]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const transferPresident = useCallback(
    async (toUserId: string, note: string) => {
      const res = await fetch("/api/admin/president/transfer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to_user_id: toUserId, note: note || null }),
      });
      if (!res.ok) await escalate(res);
      await refresh();
    },
    [escalate, refresh],
  );

  const updateUser = useCallback(
    async (
      userId: string,
      patch: Partial<{ expires_at: string; status: "active" | "suspended"; title: string }>,
    ) => {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) await escalate(res);
      const updated = (await res.json()) as AdminUserOut;
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      return updated;
    },
    [escalate],
  );

  const resetPassword = useCallback(
    async (userId: string) => {
      const res = await fetch(`/api/admin/users/${userId}/password-reset`, { method: "POST" });
      if (!res.ok) await escalate(res);
      return (await res.json()) as TemporaryPasswordOut;
    },
    [escalate],
  );

  return {
    users,
    president,
    transfers,
    loading,
    error,
    refresh,
    transferPresident,
    updateUser,
    resetPassword,
  };
}
