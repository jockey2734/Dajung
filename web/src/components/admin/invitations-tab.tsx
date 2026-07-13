"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
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
import { useInvitations } from "@/lib/use-admin-tabs";
import { formatRelativeTime } from "@/lib/relative-time";
import type { InvitationOut } from "@/types/admin";

const ACTION_ERROR_FALLBACK = "요청을 처리하지 못했습니다.";
const DEFAULT_DAYS = 7;

function StatusBadge({ status }: { status: InvitationOut["status"] }) {
  const style =
    status === "활성"
      ? "bg-tea-green-soft text-tea-green"
      : status === "사용됨"
        ? "bg-surface text-taupe border border-hairline"
        : "bg-semantic-error-soft text-semantic-error";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-caption-bold ${style}`}>
      {status}
    </span>
  );
}

export function InvitationsTab() {
  const { invitations, loading, issue, revoke } = useInvitations();
  const [issueOpen, setIssueOpen] = useState(false);
  const [note, setNote] = useState("");
  const [days, setDays] = useState(String(DEFAULT_DAYS));
  // Same one-time rule as the S20 temporary password: the plaintext code
  // lives only while this dialog stays open (S15/S19 never return it again).
  // S20 임시 비밀번호와 동일한 1회 규칙: 평문 코드는 이 다이얼로그가 열려
  // 있는 동안만 존재한다 (S15/S19는 다시 반환하지 않는다).
  const [issuedCode, setIssuedCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<InvitationOut | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function resetIssueDialog(nextOpen: boolean) {
    setIssueOpen(nextOpen);
    setIssuedCode(null);
    setCopied(false);
    setActionError(null);
    if (nextOpen) {
      setNote("");
      setDays(String(DEFAULT_DAYS));
    }
  }

  async function handleIssue() {
    setBusy(true);
    setActionError(null);
    try {
      const created = await issue(note, Number(days) || DEFAULT_DAYS);
      setIssuedCode(created.code);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
    } finally {
      setBusy(false);
    }
  }

  async function copyCode() {
    if (!issuedCode) return;
    await navigator.clipboard.writeText(issuedCode);
    setCopied(true);
  }

  if (loading && invitations.length === 0) {
    return <div className="p-8 text-center text-taupe">로딩 중...</div>;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button onClick={() => resetIssueDialog(true)}>통과번호 발급</Button>
      </div>

      {invitations.length === 0 ? (
        <p className="rounded-md border border-hairline bg-canvas p-8 text-center text-body text-taupe">
          발급된 통과번호가 없습니다.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-hairline bg-canvas">
          <table className="w-full border-collapse text-left text-body-sm">
            <thead>
              <tr className="border-b border-hairline bg-surface text-caption-bold text-taupe">
                <th className="px-4 py-2.5">상태</th>
                <th className="px-4 py-2.5">메모</th>
                <th className="px-4 py-2.5">만료</th>
                <th className="px-4 py-2.5">사용</th>
                <th className="px-4 py-2.5 w-20" />
              </tr>
            </thead>
            <tbody>
              {invitations.map((row) => (
                <tr key={row.id} className="border-b border-hairline last:border-b-0">
                  <td className="px-4 py-2.5">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-4 py-2.5">{row.note ?? "-"}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-taupe">
                    {row.expires_at.slice(0, 10)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-taupe">
                    {row.used_at ? formatRelativeTime(row.used_at) : "-"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {row.status === "활성" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-taupe hover:text-semantic-error"
                        onClick={() => {
                          setActionError(null);
                          setRevokeTarget(row);
                        }}
                      >
                        폐기
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={issueOpen} onOpenChange={resetIssueDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>통과번호 발급</DialogTitle>
            <DialogDescription>가입에 필요한 1회용 통과번호를 발급합니다.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            {issuedCode ? (
              <>
                <div className="flex items-center gap-2 rounded-lg border border-hairline bg-surface p-3">
                  <code className="flex-1 break-all font-mono text-body">{issuedCode}</code>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="통과번호 복사"
                    onClick={copyCode}
                  >
                    <Copy className="size-4" />
                  </Button>
                </div>
                {copied && <p className="text-caption text-semantic-success">복사되었습니다.</p>}
                <p className="text-body-sm text-semantic-error">
                  이 통과번호는 지금 한 번만 표시됩니다. 카톡·문자로만 전달하고 다른 곳에 기록하지
                  마세요.
                </p>
              </>
            ) : (
              <>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="invite-note">메모 (수신자, 선택)</Label>
                  <Input
                    id="invite-note"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    maxLength={1000}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="invite-days">유효 기간 (일)</Label>
                  <Input
                    id="invite-days"
                    type="number"
                    min={1}
                    value={days}
                    onChange={(e) => setDays(e.target.value)}
                  />
                </div>
              </>
            )}
            {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => resetIssueDialog(false)}>
              닫기
            </Button>
            {!issuedCode && (
              <Button disabled={busy} onClick={handleIssue}>
                발급
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!revokeTarget} onOpenChange={(o) => !o && setRevokeTarget(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>통과번호 폐기</DialogTitle>
            <DialogDescription>
              폐기하면 즉시 만료되어 가입에 사용할 수 없습니다. 기록은 삭제되지 않습니다.
            </DialogDescription>
          </DialogHeader>
          {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setRevokeTarget(null)}>
              취소
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setActionError(null);
                try {
                  await revoke(revokeTarget!.id);
                  setRevokeTarget(null);
                } catch (err) {
                  setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
                } finally {
                  setBusy(false);
                }
              }}
            >
              폐기
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
