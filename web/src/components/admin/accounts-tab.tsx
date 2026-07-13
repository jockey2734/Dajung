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
import {
  ACCOUNT_TERM_MONTHS,
  addMonthsClamped,
  dateInputToExpiresAt,
  toDateInputValue,
} from "@/lib/account-term";
import { formatRelativeTime } from "@/lib/relative-time";
import type { AdminUserOut, Role } from "@/types/admin";

const ACTION_ERROR_FALLBACK = "요청을 처리하지 못했습니다.";

const ROLE_LABELS: Record<Role, string> = {
  owner: "관리자",
  president: "회장",
  staff: "운영진",
};

function RoleBadge({ role }: { role: Role }) {
  const style =
    role === "owner"
      ? "bg-espresso text-cream"
      : role === "president"
        ? "bg-primary text-on-primary"
        : "bg-surface text-taupe border border-hairline";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-caption-bold ${style}`}>
      {ROLE_LABELS[role]}
    </span>
  );
}

export function AccountsTab({
  viewerId,
  viewerRole,
  users,
  onUpdate,
  onResetPassword,
}: {
  viewerId: string;
  viewerRole: Role;
  users: AdminUserOut[];
  onUpdate: (
    userId: string,
    patch: Partial<{ expires_at: string; status: "active" | "suspended" }>,
  ) => Promise<AdminUserOut>;
  onResetPassword: (userId: string) => Promise<{ temporary_password: string }>;
}) {
  const [extendTarget, setExtendTarget] = useState<AdminUserOut | null>(null);
  const [extendDate, setExtendDate] = useState("");
  const [suspendTarget, setSuspendTarget] = useState<AdminUserOut | null>(null);
  const [resetTarget, setResetTarget] = useState<AdminUserOut | null>(null);
  // Held only while the reset dialog is open — closing it discards the
  // plaintext for good (S19 returns it exactly once; there is no re-read).
  // 재설정 다이얼로그가 열려 있는 동안만 유지 — 닫으면 평문은 영구히 사라진다
  // (S19가 딱 한 번만 반환하며 다시 조회할 방법이 없다).
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Spec (S20): owner rows show disabled actions to a president viewer.
  // Self-suspend is 422 on the backend — disable it here too.
  // 명세 (S20): president에게 owner 행 액션은 비활성. 자기 자신 suspend는
  // 백엔드 422 — 여기서도 비활성.
  function rowActionsDisabled(user: AdminUserOut): boolean {
    return user.role === "owner" && viewerRole !== "owner";
  }

  function openExtend(user: AdminUserOut) {
    setActionError(null);
    setExtendTarget(user);
    setExtendDate(
      user.expires_at ? user.expires_at.slice(0, 10) : toDateInputValue(new Date()),
    );
  }

  async function runAction(action: () => Promise<unknown>, close: () => void) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      close();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
    } finally {
      setBusy(false);
    }
  }

  async function copyTempPassword() {
    if (!tempPassword) return;
    await navigator.clipboard.writeText(tempPassword);
    setCopied(true);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto rounded-lg border border-hairline bg-canvas">
        <table className="w-full border-collapse text-left text-body-sm">
          <thead>
            <tr className="border-b border-hairline bg-surface text-caption-bold text-taupe">
              <th className="px-4 py-2.5">이름</th>
              <th className="px-4 py-2.5">직책</th>
              <th className="px-4 py-2.5">역할</th>
              <th className="px-4 py-2.5">상태</th>
              <th className="px-4 py-2.5">임기 만료</th>
              <th className="px-4 py-2.5">최근 접속</th>
              <th className="px-4 py-2.5">액션</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const disabled = rowActionsDisabled(user);
              return (
                <tr key={user.id} className="border-b border-hairline last:border-b-0">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-ink">{user.name}</div>
                    <div className="text-caption text-taupe">{user.email}</div>
                  </td>
                  <td className="px-4 py-2.5 text-taupe">{user.title ?? "-"}</td>
                  <td className="px-4 py-2.5">
                    <RoleBadge role={user.role} />
                  </td>
                  <td className="px-4 py-2.5">
                    {user.status === "active" ? (
                      <span className="text-semantic-success">활성</span>
                    ) : (
                      <span className="text-semantic-error">중지</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-taupe">
                    {user.expires_at ? user.expires_at.slice(0, 10) : "무기한"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-taupe">
                    {user.last_seen_at ? formatRelativeTime(user.last_seen_at) : "-"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={disabled || user.role === "owner"}
                        onClick={() => openExtend(user)}
                      >
                        임기 연장
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={disabled || user.id === viewerId}
                        onClick={() => {
                          setActionError(null);
                          setSuspendTarget(user);
                        }}
                      >
                        {user.status === "active" ? "중지" : "재개"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={disabled}
                        onClick={() => {
                          setActionError(null);
                          setCopied(false);
                          setTempPassword(null);
                          setResetTarget(user);
                        }}
                      >
                        비번 재설정
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Dialog open={!!extendTarget} onOpenChange={(o) => !o && setExtendTarget(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>임기 연장 — {extendTarget?.name}</DialogTitle>
            <DialogDescription>새 임기 만료일을 지정합니다.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex items-end gap-2">
              <div className="flex flex-1 flex-col gap-1.5">
                <Label htmlFor="extend-date">만료일</Label>
                <Input
                  id="extend-date"
                  type="date"
                  value={extendDate}
                  onChange={(e) => setExtendDate(e.target.value)}
                />
              </div>
              <Button
                variant="outline"
                onClick={() =>
                  setExtendDate(toDateInputValue(addMonthsClamped(new Date(), ACCOUNT_TERM_MONTHS)))
                }
              >
                +{ACCOUNT_TERM_MONTHS}개월
              </Button>
            </div>
            {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExtendTarget(null)}>
              취소
            </Button>
            <Button
              disabled={!extendDate || busy}
              onClick={() =>
                runAction(
                  () => onUpdate(extendTarget!.id, { expires_at: dateInputToExpiresAt(extendDate) }),
                  () => setExtendTarget(null),
                )
              }
            >
              저장
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!suspendTarget} onOpenChange={(o) => !o && setSuspendTarget(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>
              {suspendTarget?.status === "active" ? "계정 중지" : "계정 재개"} — {suspendTarget?.name}
            </DialogTitle>
            <DialogDescription>
              {suspendTarget?.status === "active"
                ? "중지된 계정은 즉시 로그인과 API 사용이 차단됩니다."
                : "계정을 다시 활성화합니다."}
            </DialogDescription>
          </DialogHeader>
          {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSuspendTarget(null)}>
              취소
            </Button>
            <Button
              variant={suspendTarget?.status === "active" ? "destructive" : "default"}
              disabled={busy}
              onClick={() =>
                runAction(
                  () =>
                    onUpdate(suspendTarget!.id, {
                      status: suspendTarget!.status === "active" ? "suspended" : "active",
                    }),
                  () => setSuspendTarget(null),
                )
              }
            >
              확인
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!resetTarget}
        onOpenChange={(o) => {
          if (!o) {
            setResetTarget(null);
            setTempPassword(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>비밀번호 재설정 — {resetTarget?.name}</DialogTitle>
            <DialogDescription>
              임시 비밀번호를 발급합니다. 대상자는 다음 로그인에서 비밀번호를 반드시 변경해야
              합니다.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            {tempPassword ? (
              <>
                <div className="flex items-center gap-2 rounded-lg border border-hairline bg-surface p-3">
                  <code className="flex-1 break-all font-mono text-body">{tempPassword}</code>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="임시 비밀번호 복사"
                    onClick={copyTempPassword}
                  >
                    <Copy className="size-4" />
                  </Button>
                </div>
                {copied && <p className="text-caption text-semantic-success">복사되었습니다.</p>}
                <p className="text-body-sm text-semantic-error">
                  이 비밀번호는 지금 한 번만 표시됩니다. 카톡·문자로만 전달하고 다른 곳에 기록하지
                  마세요.
                </p>
              </>
            ) : (
              <p className="text-body-sm text-taupe">
                발급된 임시 비밀번호는 이 창에서 한 번만 표시됩니다.
              </p>
            )}
            {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setResetTarget(null);
                setTempPassword(null);
              }}
            >
              닫기
            </Button>
            {!tempPassword && (
              <Button
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setActionError(null);
                  try {
                    const result = await onResetPassword(resetTarget!.id);
                    setTempPassword(result.temporary_password);
                  } catch (err) {
                    setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                임시 비밀번호 발급
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
