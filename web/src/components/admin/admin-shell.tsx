"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TransferTab } from "@/components/admin/transfer-tab";
import { AccountsTab } from "@/components/admin/accounts-tab";
import { useAdmin } from "@/lib/use-admin";
import type { Role } from "@/types/admin";

// Tab surface (webapp-spec S20): 권한 이양·계정 now, 시스템 = owner-only
// placeholder. 통과번호·학기별 명단·문서 are S21 — hidden until then.
// 탭 구성 (webapp-spec S20): 지금은 권한 이양·계정, 시스템 = owner 전용
// placeholder. 통과번호·학기별 명단·문서는 S21 — 그때까지 숨김.
export function AdminShell({ viewerId, viewerRole }: { viewerId: string; viewerRole: Role }) {
  const {
    users,
    president,
    transfers,
    loading,
    error,
    transferPresident,
    updateUser,
    resetPassword,
  } = useAdmin();

  if (loading && users.length === 0) {
    return <div className="p-8 text-center text-taupe">로딩 중...</div>;
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 sm:p-6">
      <h1 className="text-heading-2 font-semibold tracking-tight text-ink">관리자</h1>
      {error && (
        <div className="rounded-md border border-semantic-error/20 bg-semantic-error-soft p-3 text-sm text-semantic-error">
          {error}
        </div>
      )}
      <Tabs defaultValue="transfer">
        <TabsList className="w-full sm:w-fit">
          <TabsTrigger value="transfer">권한 이양</TabsTrigger>
          <TabsTrigger value="accounts">계정</TabsTrigger>
          {viewerRole === "owner" && <TabsTrigger value="system">시스템</TabsTrigger>}
        </TabsList>
        <TabsContent value="transfer" className="pt-2">
          <TransferTab
            viewerRole={viewerRole}
            president={president}
            users={users}
            transfers={transfers}
            onTransfer={transferPresident}
          />
        </TabsContent>
        <TabsContent value="accounts" className="pt-2">
          <AccountsTab
            viewerId={viewerId}
            viewerRole={viewerRole}
            users={users}
            onUpdate={updateUser}
            onResetPassword={resetPassword}
          />
        </TabsContent>
        {viewerRole === "owner" && (
          <TabsContent value="system" className="pt-2">
            <div className="rounded-lg border border-hairline bg-canvas p-6 text-body text-taupe">
              페르소나·시스템 설정은 SSH로 관리합니다. 이 탭은 추후 확장 예정입니다.
            </div>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
