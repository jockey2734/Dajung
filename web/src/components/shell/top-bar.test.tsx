import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("next-auth/react", () => ({ signOut: vi.fn() }));
// PageSwitcher (rendered inside TopBar) reads the pathname for its active pill.
// TopBar 안에 렌더되는 PageSwitcher가 활성 표시용으로 pathname을 읽는다.
vi.mock("next/navigation", () => ({ usePathname: () => "/chat" }));

const { TopBar } = await import("@/components/shell/top-bar");

afterEach(() => {
  cleanup();
});

describe("TopBar admin entry (webapp-spec S20)", () => {
  it("shows the admin shield for owner and president", () => {
    render(<TopBar userName="운하" role="owner" />);
    expect(screen.getByRole("link", { name: "관리자 페이지" })).toHaveAttribute("href", "/admin");
    cleanup();

    render(<TopBar userName="회장" role="president" />);
    expect(screen.getByRole("link", { name: "관리자 페이지" })).toBeInTheDocument();
  });

  it("hides the admin shield for staff and when me is unavailable", () => {
    render(<TopBar userName="운영진" role="staff" />);
    expect(screen.queryByRole("link", { name: "관리자 페이지" })).not.toBeInTheDocument();
    cleanup();

    render(<TopBar userName="누군가" role={null} />);
    expect(screen.queryByRole("link", { name: "관리자 페이지" })).not.toBeInTheDocument();
  });
});
