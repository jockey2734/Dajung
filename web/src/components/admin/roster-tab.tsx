"use client";

import { useMemo, useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRoster } from "@/lib/use-admin-tabs";
import { currentSemester, isPastSemester, nextSemester } from "@/lib/semester";
import type { AdminUserOut, RosterOut } from "@/types/admin";

const ACTION_ERROR_FALLBACK = "요청을 처리하지 못했습니다.";

// The five standing departments (25-1 OT); free text stays possible via the
// datalist — the backend accepts any 1–30 char string.
// 상설 5부서 (25-1 OT). datalist라 자유 입력도 가능 — 백엔드는 1~30자 아무
// 문자열이나 받는다.
const DEPARTMENT_PRESETS = ["회장단", "기획부", "집행부", "홍보부", "총무부"];

// Registering someone on a current/future semester roster auto-extends their
// account term server-side (S19) — surfaced to the admin per spec S21.
// 현재/미래 학기 명단 등록은 서버가 계정 임기를 자동 연장한다(S19) — 명세
// S21대로 관리자에게 고지한다.
const EXTENSION_NOTICE = "현재 학기 명단 등록 시 임기가 학기 시작+7개월로 연장됩니다";

export function RosterTab({ users }: { users: AdminUserOut[] }) {
  const { rows, loading, addRow, updateRow, deleteRow } = useRoster();
  const [semester, setSemester] = useState(currentSemester());
  const [adding, setAdding] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<RosterOut | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [formDepartment, setFormDepartment] = useState("");
  const [formName, setFormName] = useState("");
  const [formPosition, setFormPosition] = useState("");
  const [formUserId, setFormUserId] = useState("");

  const semesterOptions = useMemo(() => {
    const now = currentSemester();
    const options = new Set([...rows.map((row) => row.semester), now, nextSemester(now)]);
    return [...options].sort().reverse();
  }, [rows]);

  const visibleRows = useMemo(
    () =>
      rows
        .filter((row) => row.semester === semester)
        .sort(
          (a, b) =>
            DEPARTMENT_PRESETS.indexOf(a.department) - DEPARTMENT_PRESETS.indexOf(b.department) ||
            a.department.localeCompare(b.department, "ko") ||
            a.member_name.localeCompare(b.member_name, "ko"),
        ),
    [rows, semester],
  );

  // Past semesters are a read-only record (spec S21) — edits happen only on
  // the current/future roster, where they also drive term extension.
  // 과거 학기는 열람 전용 기록 (명세 S21) — 편집은 임기 연장과 연동되는
  // 현재/미래 학기에서만.
  const readOnly = isPastSemester(semester);

  const userName = (userId: string | null) =>
    userId ? (users.find((u) => u.id === userId)?.name ?? "(알 수 없음)") : null;

  function openAdd() {
    setActionError(null);
    setFormDepartment("");
    setFormName("");
    setFormPosition("");
    setFormUserId("");
    setAdding(true);
  }

  async function handleAdd() {
    if (!formDepartment.trim() || !formName.trim() || busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await addRow({
        semester,
        department: formDepartment.trim(),
        member_name: formName.trim(),
        position: formPosition.trim() || null,
        user_id: formUserId || null,
      });
      setAdding(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
    } finally {
      setBusy(false);
    }
  }

  if (loading && rows.length === 0) {
    return <div className="p-8 text-center text-taupe">로딩 중...</div>;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Label htmlFor="roster-semester" className="text-taupe">
            학기
          </Label>
          <select
            id="roster-semester"
            value={semester}
            onChange={(e) => setSemester(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            {semesterOptions.map((option) => (
              <option key={option} value={option}>
                {option}
                {isPastSemester(option) ? " (기록)" : ""}
              </option>
            ))}
          </select>
        </div>
        {!readOnly && <Button onClick={openAdd}>행 추가</Button>}
      </div>

      {readOnly && (
        <p className="rounded-md border border-hairline bg-surface p-3 text-body-sm text-taupe">
          과거 학기 명단은 열람·기록 전용입니다.
        </p>
      )}

      {visibleRows.length === 0 ? (
        <p className="rounded-md border border-hairline bg-canvas p-8 text-center text-body text-taupe">
          {semester} 명단이 비어 있습니다.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-hairline bg-canvas">
          <table className="w-full border-collapse text-left text-body-sm">
            <thead>
              <tr className="border-b border-hairline bg-surface text-caption-bold text-taupe">
                <th className="px-4 py-2.5">부서</th>
                <th className="px-4 py-2.5">이름</th>
                <th className="px-4 py-2.5">직책</th>
                <th className="px-4 py-2.5">연결 계정</th>
                {!readOnly && <th className="px-4 py-2.5 w-12" />}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <tr key={row.id} className="border-b border-hairline last:border-b-0">
                  <td className="px-4 py-2.5">{row.department}</td>
                  <td className="px-4 py-2.5 font-medium text-ink">{row.member_name}</td>
                  <td className="px-4 py-2.5 text-taupe">{row.position ?? "-"}</td>
                  <td className="px-4 py-2.5">
                    {readOnly ? (
                      <span className="text-taupe">{userName(row.user_id) ?? "-"}</span>
                    ) : (
                      <select
                        aria-label={`${row.member_name} 연결 계정`}
                        value={row.user_id ?? ""}
                        onChange={(e) =>
                          void updateRow(row.id, { user_id: e.target.value || null }).catch(
                            (err) =>
                              setActionError(
                                err instanceof Error ? err.message : ACTION_ERROR_FALLBACK,
                              ),
                          )
                        }
                        className="h-8 rounded-md border border-input bg-background px-2 text-sm"
                      >
                        <option value="">(없음)</option>
                        {users.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                  {!readOnly && (
                    <td className="px-4 py-2.5 text-right">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${row.member_name} 삭제`}
                        className="text-taupe hover:text-semantic-error"
                        onClick={() => {
                          setActionError(null);
                          setDeleteTarget(row);
                        }}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!readOnly && <p className="text-caption text-taupe">{EXTENSION_NOTICE}</p>}
      {actionError && !adding && !deleteTarget && (
        <p className="text-body-sm text-semantic-error">{actionError}</p>
      )}

      <Dialog open={adding} onOpenChange={(o) => !o && setAdding(false)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>명단 행 추가 — {semester}</DialogTitle>
            <DialogDescription>{EXTENSION_NOTICE}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="roster-department">부서</Label>
              <Input
                id="roster-department"
                list="roster-department-presets"
                value={formDepartment}
                onChange={(e) => setFormDepartment(e.target.value)}
                maxLength={30}
              />
              <datalist id="roster-department-presets">
                {DEPARTMENT_PRESETS.map((preset) => (
                  <option key={preset} value={preset} />
                ))}
              </datalist>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="roster-name">이름</Label>
              <Input
                id="roster-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                maxLength={100}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="roster-position">직책 (선택)</Label>
              <Input
                id="roster-position"
                value={formPosition}
                onChange={(e) => setFormPosition(e.target.value)}
                maxLength={30}
                placeholder="부장 / 차장"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="roster-user">연결 계정 (선택)</Label>
              <select
                id="roster-user"
                value={formUserId}
                onChange={(e) => setFormUserId(e.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">(없음)</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.email})
                  </option>
                ))}
              </select>
            </div>
            {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAdding(false)}>
              취소
            </Button>
            <Button disabled={!formDepartment.trim() || !formName.trim() || busy} onClick={handleAdd}>
              추가
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>명단 행 삭제</DialogTitle>
            <DialogDescription>
              {deleteTarget?.semester} {deleteTarget?.department} {deleteTarget?.member_name} 행을
              삭제합니다. 이미 연장된 계정 임기는 되돌리지 않습니다.
            </DialogDescription>
          </DialogHeader>
          {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              취소
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setActionError(null);
                try {
                  await deleteRow(deleteTarget!.id);
                  setDeleteTarget(null);
                } catch (err) {
                  setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
                } finally {
                  setBusy(false);
                }
              }}
            >
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
