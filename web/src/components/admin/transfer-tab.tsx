"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
import { flashToast } from "@/components/shell/toast-provider";
import { formatRelativeTime } from "@/lib/relative-time";
import type { AdminUserOut, PresidentTransferOut, PresidentUserOut, Role } from "@/types/admin";

const TRANSFER_ERROR_FALLBACK = "권한 이양에 실패했습니다.";

export function TransferTab({
  viewerRole,
  president,
  users,
  transfers,
  onTransfer,
}: {
  viewerRole: Role;
  president: PresidentUserOut | null;
  users: AdminUserOut[];
  transfers: PresidentTransferOut[];
  onTransfer: (toUserId: string, note: string) => Promise<void>;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  // Two-step arming (webapp-spec S20): the first click only reveals the
  // warning; the actual API call needs a second click on the confirm copy.
  // 2단계 무장 (webapp-spec S20): 첫 클릭은 경고만 펼치고, 실제 API 호출은
  // 확인 문구 버튼을 한 번 더 클릭해야 나간다.
  const [armed, setArmed] = useState(false);
  const [targetId, setTargetId] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const candidates = users.filter((u) => u.role === "staff" && u.status === "active");

  function resetDialog(nextOpen: boolean) {
    setOpen(nextOpen);
    setArmed(false);
    setFormError(null);
    if (!nextOpen) {
      setTargetId("");
      setNote("");
    }
  }

  async function confirmTransfer() {
    if (!targetId || submitting) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await onTransfer(targetId, note);
      if (viewerRole === "president") {
        // The viewer just demoted themselves — every further admin call
        // would 403, so leave immediately (spec: exit to /chat + toast).
        // 방금 스스로를 강등했다 — 이후 모든 admin 호출이 403이므로 즉시
        // 이탈한다 (명세: /chat 이탈 + 토스트).
        flashToast("권한 이양이 완료되었습니다. 관리자 권한이 해제되었습니다.");
        router.push("/chat");
        return;
      }
      resetDialog(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : TRANSFER_ERROR_FALLBACK);
      setArmed(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-lg border border-hairline bg-canvas p-4">
        <h2 className="text-heading-4 text-ink">현재 회장</h2>
        {president ? (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-body text-espresso">
            <span className="font-semibold">{president.name}</span>
            <span className="text-taupe">{president.email}</span>
            {president.expires_at && (
              <span className="text-caption text-taupe">
                임기 만료 {president.expires_at.slice(0, 10)}
              </span>
            )}
          </div>
        ) : (
          <p className="mt-2 text-body text-taupe">임명된 회장이 없습니다.</p>
        )}
        <Button className="mt-4" onClick={() => resetDialog(true)}>
          권한 이양
        </Button>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-heading-4 text-ink">이양 이력</h2>
        {transfers.length === 0 ? (
          <p className="text-body-sm text-taupe">이양 기록이 없습니다.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-hairline bg-canvas">
            <table className="w-full border-collapse text-left text-body-sm">
              <thead>
                <tr className="border-b border-hairline bg-surface text-caption-bold text-taupe">
                  <th className="px-4 py-2.5">일시</th>
                  <th className="px-4 py-2.5">이전 회장</th>
                  <th className="px-4 py-2.5">새 회장</th>
                  <th className="px-4 py-2.5">처리자</th>
                  <th className="px-4 py-2.5">메모</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map((row) => (
                  <tr key={row.id} className="border-b border-hairline last:border-b-0">
                    <td className="whitespace-nowrap px-4 py-2.5 text-taupe">
                      {formatRelativeTime(row.created_at)}
                    </td>
                    <td className="px-4 py-2.5">{row.from_user?.name ?? "(최초 임명)"}</td>
                    <td className="px-4 py-2.5 font-medium">{row.to_user.name}</td>
                    <td className="px-4 py-2.5">{row.actor.name}</td>
                    <td className="px-4 py-2.5 text-taupe">{row.note ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Dialog open={open} onOpenChange={resetDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>회장 권한 이양</DialogTitle>
            <DialogDescription>
              차기 회장에게 관리자 권한을 넘깁니다. 이력은 영구 보존됩니다.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="transfer-target">차기 회장</Label>
              <select
                id="transfer-target"
                value={targetId}
                onChange={(e) => {
                  setTargetId(e.target.value);
                  setArmed(false);
                }}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">운영진 선택</option>
                {candidates.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.email})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="transfer-note">인계 메모 (선택)</Label>
              <Input
                id="transfer-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={1000}
              />
            </div>
            {armed && (
              <div className="rounded-lg border border-semantic-error bg-semantic-error-soft p-3 text-body-sm text-semantic-error">
                {viewerRole === "president"
                  ? "이양 즉시 본인의 관리자 권한이 사라집니다. 계속하려면 아래 확인 버튼을 다시 눌러 주세요."
                  : president === null
                    ? "임명 즉시 해당 운영진이 관리자(회장) 권한을 갖습니다. 계속하려면 아래 확인 버튼을 다시 눌러 주세요."
                  : "이양 즉시 기존 회장의 관리자 권한이 사라집니다. 계속하려면 아래 확인 버튼을 다시 눌러 주세요."}
              </div>
            )}
            {formError && <p className="text-body-sm text-semantic-error">{formError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => resetDialog(false)}>
              취소
            </Button>
            {armed ? (
              <Button variant="destructive" disabled={!targetId || submitting} onClick={confirmTransfer}>
                권한 이양 확인
              </Button>
            ) : (
              <Button disabled={!targetId} onClick={() => setArmed(true)}>
                권한 이양
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
