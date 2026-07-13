import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FileEntry } from "@/types/files";

// Stable router identity — see invitations-tab.test.tsx.
// 안정된 router identity — invitations-tab.test.tsx 참고.
const routerMock = { push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => routerMock }));
vi.mock("next-auth/react", () => ({ signOut: vi.fn() }));

const { DocsTab } = await import("@/components/admin/docs-tab");

const fileFixture: FileEntry = {
  doc_id: "doc-1",
  source_file: "다도_기초.md",
  doc_type: "knowledge",
  semester: null,
  restricted: false,
  chunk_count: 4,
};

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    // Backend should never include 사건사고 (ADR-013) — the fixture includes
    // it anyway to prove the FE's second-layer filter.
    // 백엔드는 사건사고를 절대 포함하면 안 되지만(ADR-013), FE의 2차 필터를
    // 증명하기 위해 픽스처에 일부러 넣는다.
    if (url === "/api/admin/docs/folders") {
      return Response.json(["회의록", "사건사고", "세미나"]);
    }
    if (url === "/api/files") {
      return Response.json({ files: [fileFixture] });
    }
    if (url === "/api/admin/docs/doc-1" && init?.method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("DocsTab folder whitelist (webapp-spec S21 / ADR-013)", () => {
  it("never offers 사건사고 in the upload folder dropdown", async () => {
    const user = userEvent.setup();
    render(<DocsTab />);

    await user.click(await screen.findByRole("button", { name: "문서 업로드" }));
    const select = await screen.findByLabelText("폴더");
    const options = within(select).getAllByRole("option").map((o) => o.textContent);

    expect(options).toContain("회의록");
    expect(options).toContain("세미나");
    expect(options).not.toContain("사건사고");
  });
});

describe("DocsTab delete confirm flow (webapp-spec S21)", () => {
  it("deletes only after the confirm dialog — cancel sends nothing", async () => {
    const user = userEvent.setup();
    render(<DocsTab />);

    const deleteCalls = () =>
      fetchMock.mock.calls.filter(
        ([, init]) => (init as RequestInit | undefined)?.method === "DELETE",
      );

    await user.click((await screen.findAllByRole("button", { name: "다도_기초.md 삭제" }))[0]);
    expect(
      await screen.findByText("인덱스에서 제거되고 원본은 휴지통으로 이동합니다."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "취소" }));
    expect(deleteCalls()).toHaveLength(0);

    await user.click(screen.getAllByRole("button", { name: "다도_기초.md 삭제" })[0]);
    await user.click(await screen.findByRole("button", { name: "삭제" }));

    expect(deleteCalls()).toHaveLength(1);
    expect(String(deleteCalls()[0][0])).toBe("/api/admin/docs/doc-1");
  });
});
