import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AdminUserOut } from "@/types/admin";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: vi.fn() }),
}));

const { TransferTab } = await import("@/components/admin/transfer-tab");

afterEach(() => {
  cleanup();
  pushMock.mockReset();
});

const staffUser: AdminUserOut = {
  id: "staff-1",
  name: "차기 회장",
  email: "next@example.com",
  title: null,
  role: "staff",
  status: "active",
  expires_at: "2027-01-01T00:00:00Z",
  last_seen_at: null,
  must_change_password: false,
};

function renderTab(onTransfer = vi.fn().mockResolvedValue(undefined)) {
  render(
    <TransferTab
      viewerRole="owner"
      president={null}
      users={[staffUser]}
      transfers={[]}
      onTransfer={onTransfer}
    />,
  );
  return onTransfer;
}

describe("TransferTab double confirm (webapp-spec S20)", () => {
  it("does not call the API on the first click — only after the confirm re-click", async () => {
    const user = userEvent.setup();
    const onTransfer = renderTab();

    await user.click(screen.getByRole("button", { name: "권한 이양" }));
    await user.selectOptions(screen.getByLabelText("차기 회장"), "staff-1");

    // First click arms the dialog: warning appears, nothing is sent yet.
    // 첫 클릭은 무장만: 경고가 뜨고 아직 아무것도 전송되지 않는다.
    await user.click(screen.getByRole("button", { name: "권한 이양" }));
    expect(onTransfer).not.toHaveBeenCalled();
    expect(screen.getByText(/관리자 권한이 사라집니다/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "권한 이양 확인" }));
    expect(onTransfer).toHaveBeenCalledWith("staff-1", "");
  });

  it("disarms when the selected target changes", async () => {
    const user = userEvent.setup();
    const onTransfer = renderTab();

    await user.click(screen.getByRole("button", { name: "권한 이양" }));
    await user.selectOptions(screen.getByLabelText("차기 회장"), "staff-1");
    await user.click(screen.getByRole("button", { name: "권한 이양" }));
    expect(screen.getByRole("button", { name: "권한 이양 확인" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("차기 회장"), "");
    expect(screen.queryByRole("button", { name: "권한 이양 확인" })).not.toBeInTheDocument();
    expect(onTransfer).not.toHaveBeenCalled();
  });
});
