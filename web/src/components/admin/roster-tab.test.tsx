import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RosterOut } from "@/types/admin";
import { currentSemester } from "@/lib/semester";

// Stable router identity — see invitations-tab.test.tsx.
// 안정된 router identity — invitations-tab.test.tsx 참고.
const routerMock = { push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => routerMock }));
vi.mock("next-auth/react", () => ({ signOut: vi.fn() }));

const { RosterTab } = await import("@/components/admin/roster-tab");

const semester = currentSemester();

const existingRow: RosterOut = {
  id: "row-1",
  semester,
  department: "총무부",
  member_name: "기존 부장",
  position: "부장",
  user_id: null,
  created_at: "2026-07-01T00:00:00Z",
};

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/admin/roster" && init?.method === "POST") {
      return Response.json({ ...existingRow, id: "row-2", member_name: "새 차장" }, { status: 201 });
    }
    if (url === "/api/admin/roster") {
      return Response.json([existingRow]);
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("RosterTab term-extension notice (webapp-spec S21)", () => {
  it("renders the extension notice on the current-semester roster and in the add dialog", async () => {
    const user = userEvent.setup();
    render(<RosterTab users={[]} />);

    expect(
      await screen.findByText("현재 학기 명단 등록 시 임기가 학기 시작+7개월로 연장됩니다"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "행 추가" }));
    // The dialog repeats the notice right where the admin commits the row.
    // 관리자가 행을 확정하는 자리에서 다이얼로그가 고지를 반복한다.
    expect(
      screen.getAllByText("현재 학기 명단 등록 시 임기가 학기 시작+7개월로 연장됩니다"),
    ).toHaveLength(2);

    await user.type(screen.getByLabelText("부서"), "총무부");
    await user.type(screen.getByLabelText("이름"), "새 차장");
    await user.click(screen.getByRole("button", { name: "추가" }));

    const posts = fetchMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String((posts[0][1] as RequestInit).body))).toMatchObject({
      semester,
      department: "총무부",
      member_name: "새 차장",
    });
  });
});
