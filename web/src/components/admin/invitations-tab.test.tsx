import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Stable router identity, like the real hook — a fresh object per render
// would loop the hooks' escalate→refresh effect chain.
// 실제 훅처럼 안정된 router identity — 렌더마다 새 객체면 훅의
// escalate→refresh 이펙트 체인이 무한 반복된다.
const routerMock = { push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => routerMock }));
vi.mock("next-auth/react", () => ({ signOut: vi.fn() }));

const { InvitationsTab } = await import("@/components/admin/invitations-tab");

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/admin/invitations" && init?.method === "POST") {
      return Response.json(
        {
          id: "inv-1",
          code: "PLAINTEXT-CODE-1",
          note: null,
          expires_at: "2026-07-20T00:00:00Z",
        },
        { status: 201 },
      );
    }
    if (url === "/api/admin/invitations") {
      return Response.json([]);
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("InvitationsTab one-time code (webapp-spec S21)", () => {
  it("shows the issued plaintext once — reopening the dialog shows the form, not the code", async () => {
    const user = userEvent.setup();
    render(<InvitationsTab />);

    await user.click(await screen.findByRole("button", { name: "통과번호 발급" }));
    await user.click(screen.getByRole("button", { name: "발급" }));

    expect(await screen.findByText("PLAINTEXT-CODE-1")).toBeInTheDocument();
    expect(screen.getByText(/한 번만 표시됩니다.*카톡·문자로만 전달/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "닫기" }));
    await user.click(screen.getByRole("button", { name: "통과번호 발급" }));

    expect(screen.queryByText("PLAINTEXT-CODE-1")).not.toBeInTheDocument();
    const issuePosts = fetchMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(issuePosts).toHaveLength(1);
  });
});
