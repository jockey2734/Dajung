"use client";

import { useCallback, useEffect, useState } from "react";
import { useAdminEscalate } from "@/lib/admin-escalate";
import type {
  DocumentUploadOut,
  InvitationCreatedOut,
  InvitationOut,
  RosterOut,
} from "@/types/admin";

export function useInvitations() {
  const escalate = useAdminEscalate();
  const [invitations, setInvitations] = useState<InvitationOut[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/invitations");
      if (!res.ok) await escalate(res);
      setInvitations((await res.json()) as InvitationOut[]);
    } finally {
      setLoading(false);
    }
  }, [escalate]);

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, [refresh]);

  const issue = useCallback(
    async (note: string, days: number) => {
      const res = await fetch("/api/admin/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: note || null, days }),
      });
      if (!res.ok) await escalate(res);
      const created = (await res.json()) as InvitationCreatedOut;
      await refresh().catch(() => undefined);
      return created;
    },
    [escalate, refresh],
  );

  const revoke = useCallback(
    async (invitationId: string) => {
      const res = await fetch(`/api/admin/invitations/${invitationId}/revoke`, {
        method: "POST",
      });
      if (!res.ok) await escalate(res);
      const revoked = (await res.json()) as InvitationOut;
      setInvitations((prev) => prev.map((row) => (row.id === revoked.id ? revoked : row)));
    },
    [escalate],
  );

  return { invitations, loading, issue, revoke };
}

// Fetches the whole roster (a club-sized table) so the semester selector can
// list every semester that actually has rows; filtering is client-side.
// 명단 전체를 가져온다(동아리 규모 테이블) — 학기 셀렉트가 실제 행이 있는
// 학기를 모두 나열할 수 있게. 필터링은 클라이언트에서.
export function useRoster() {
  const escalate = useAdminEscalate();
  const [rows, setRows] = useState<RosterOut[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/roster");
      if (!res.ok) await escalate(res);
      setRows((await res.json()) as RosterOut[]);
    } finally {
      setLoading(false);
    }
  }, [escalate]);

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, [refresh]);

  const addRow = useCallback(
    async (row: {
      semester: string;
      department: string;
      member_name: string;
      position: string | null;
      user_id: string | null;
    }) => {
      const res = await fetch("/api/admin/roster", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(row),
      });
      if (!res.ok) await escalate(res);
      await refresh().catch(() => undefined);
    },
    [escalate, refresh],
  );

  const updateRow = useCallback(
    async (
      rosterId: string,
      patch: Partial<{
        department: string;
        member_name: string;
        position: string | null;
        user_id: string | null;
      }>,
    ) => {
      const res = await fetch(`/api/admin/roster/${rosterId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) await escalate(res);
      const updated = (await res.json()) as RosterOut;
      setRows((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
    },
    [escalate],
  );

  const deleteRow = useCallback(
    async (rosterId: string) => {
      const res = await fetch(`/api/admin/roster/${rosterId}`, { method: "DELETE" });
      if (!res.ok) await escalate(res);
      setRows((prev) => prev.filter((row) => row.id !== rosterId));
    },
    [escalate],
  );

  return { rows, loading, addRow, updateRow, deleteRow };
}

export function useAdminDocs() {
  const escalate = useAdminEscalate();
  const [folders, setFolders] = useState<string[]>([]);

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        const res = await fetch("/api/admin/docs/folders");
        if (!res.ok) await escalate(res);
        const list = (await res.json()) as string[];
        // Backend already excludes 사건사고 (ADR-013) — filter again here as
        // the second layer, same double-guard stance as retrieval.
        // 백엔드가 이미 사건사고를 제외(ADR-013) — 검색과 같은 이중 방어
        // 원칙으로 여기서 한 번 더 거른다.
        if (!ignore) setFolders(list.filter((name) => name !== "사건사고").sort());
      } catch {
        if (!ignore) setFolders([]);
      }
    }
    void load();
    return () => {
      ignore = true;
    };
  }, [escalate]);

  const upload = useCallback(
    async (folder: string, file: File) => {
      const form = new FormData();
      form.append("folder", folder);
      form.append("file", file);
      const res = await fetch("/api/admin/docs", { method: "POST", body: form });
      if (!res.ok) await escalate(res);
      return (await res.json()) as DocumentUploadOut;
    },
    [escalate],
  );

  const removeDocument = useCallback(
    async (docId: string) => {
      const res = await fetch(`/api/admin/docs/${docId}`, { method: "DELETE" });
      if (!res.ok) await escalate(res);
    },
    [escalate],
  );

  return { folders, upload, removeDocument };
}
