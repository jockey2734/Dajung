"use client";

import { useCallback, useEffect, useState } from "react";
import { useAdminEscalate } from "@/lib/admin-escalate";
import type {
  AdminUserOut,
  PresidentTransferOut,
  PresidentUserOut,
  TemporaryPasswordOut,
} from "@/types/admin";

const GENERIC_ERROR = "요청을 처리하지 못했습니다.";

export function useAdmin() {
  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [president, setPresident] = useState<PresidentUserOut | null>(null);
  const [transfers, setTransfers] = useState<PresidentTransferOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Shared 403/account_expired handling — extracted to admin-escalate.ts so
  // the S21 tab hooks use the identical policy.
  // 403/account_expired 공통 처리 — S21 탭 훅들이 동일 정책을 쓰도록
  // admin-escalate.ts로 추출.
  const escalate = useAdminEscalate();

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
