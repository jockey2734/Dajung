import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountsTab } from "@/components/admin/accounts-tab";
import type { AdminUserOut, Role } from "@/types/admin";

afterEach(() => {
  cleanup();
});

const owner: AdminUserOut = {
  id: "owner-1",
  name: "임운하",
  email: "owner@example.com",
  title: null,
  role: "owner",
  status: "active",
  expires_at: null,
  last_seen_at: null,
  must_change_password: false,
};

const staff: AdminUserOut = {
  id: "staff-1",
  name: "운영진",
  email: "staff@example.com",
  title: "총무부장",
  role: "staff",
  status: "active",
  expires_at: "2027-01-01T00:00:00Z",
  last_seen_at: null,
  must_change_password: false,
};

function renderTab({
  viewerRole = "owner" as Role,
  viewerId = "owner-1",
  onResetPassword = vi.fn().mockResolvedValue({ temporary_password: "temp-secret-12" }),
} = {}) {
  render(
    <AccountsTab
      viewerId={viewerId}
      viewerRole={viewerRole}
      users={[owner, staff]}
      onUpdate={vi.fn()}
      onResetPassword={onResetPassword}
    />,
  );
  return onResetPassword;
}

describe("AccountsTab temporary password (webapp-spec S20)", () => {
  it("shows the plaintext exactly once — reopening the dialog shows nothing", async () => {
    const user = userEvent.setup();
    const onResetPassword = renderTab();

    const resetButtons = screen.getAllByRole("button", { name: "비번 재설정" });
    await user.click(resetButtons[1]);
    await user.click(screen.getByRole("button", { name: "임시 비밀번호 발급" }));

    expect(await screen.findByText("temp-secret-12")).toBeInTheDocument();
    expect(screen.getByText(/한 번만 표시됩니다.*카톡·문자로만 전달/)).toBeInTheDocument();
    expect(onResetPassword).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "닫기" }));
    await user.click(screen.getAllByRole("button", { name: "비번 재설정" })[1]);

    // The plaintext is gone for good — no auto re-issue on reopen.
    // 평문은 영구히 사라졌다 — 다시 열어도 자동 재발급되지 않는다.
    expect(screen.queryByText("temp-secret-12")).not.toBeInTheDocument();
    expect(onResetPassword).toHaveBeenCalledTimes(1);
  });
});

describe("AccountsTab owner-row protection (webapp-spec S20)", () => {
  it("disables owner-row actions for a president viewer", () => {
    renderTab({ viewerRole: "president", viewerId: "president-1" });

    // Row order matches the users prop: index 0 = owner row.
    // 행 순서는 users prop 순서 — index 0 = owner 행.
    const suspendButtons = screen.getAllByRole("button", { name: "중지" });
    const resetButtons = screen.getAllByRole("button", { name: "비번 재설정" });
    expect(suspendButtons[0]).toBeDisabled();
    expect(resetButtons[0]).toBeDisabled();
    expect(suspendButtons[1]).toBeEnabled();
    expect(resetButtons[1]).toBeEnabled();
  });

  it("disables self-suspend even for the owner viewer", () => {
    renderTab();
    expect(screen.getAllByRole("button", { name: "중지" })[0]).toBeDisabled();
  });
});
