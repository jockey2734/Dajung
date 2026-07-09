import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionSidebar } from "./session-sidebar";

const SESSIONS = [{ id: "s1", title: "25-1 예산안 문의", lastMessageAt: null, messageCount: 2 }];
const noop = () => {};

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
});

describe("SessionSidebar collapse persistence (webapp-spec S4: localStorage `dajung.sidebar`)", () => {
  it("starts expanded when localStorage has no saved preference", () => {
    render(
      <SessionSidebar sessions={SESSIONS} activeSessionId={null} onSelect={noop} onNewChat={noop} onDelete={noop} />,
    );
    expect(screen.getByText("새 채팅")).toBeInTheDocument();
  });

  it("collapses on toggle click and writes the preference to localStorage", async () => {
    const user = userEvent.setup();
    render(
      <SessionSidebar sessions={SESSIONS} activeSessionId={null} onSelect={noop} onNewChat={noop} onDelete={noop} />,
    );
    await user.click(screen.getByLabelText("세션 사이드바 접기"));
    expect(screen.queryByText("새 채팅")).not.toBeInTheDocument();
    expect(window.localStorage.getItem("dajung.sidebar")).toBe("collapsed");
  });

  it("starts collapsed when localStorage already says collapsed", () => {
    window.localStorage.setItem("dajung.sidebar", "collapsed");
    render(
      <SessionSidebar sessions={SESSIONS} activeSessionId={null} onSelect={noop} onNewChat={noop} onDelete={noop} />,
    );
    expect(screen.queryByText("새 채팅")).not.toBeInTheDocument();
    expect(screen.getByLabelText("세션 사이드바 펼치기")).toBeInTheDocument();
  });

  it("expanding again writes 'expanded' back to localStorage", async () => {
    window.localStorage.setItem("dajung.sidebar", "collapsed");
    const user = userEvent.setup();
    render(
      <SessionSidebar sessions={SESSIONS} activeSessionId={null} onSelect={noop} onNewChat={noop} onDelete={noop} />,
    );
    await user.click(screen.getByLabelText("세션 사이드바 펼치기"));
    expect(screen.getByText("새 채팅")).toBeInTheDocument();
    expect(window.localStorage.getItem("dajung.sidebar")).toBe("expanded");
  });
});

describe("SessionSidebar interactions", () => {
  it("calls onSelect with the session id when a row is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <SessionSidebar
        sessions={SESSIONS}
        activeSessionId={null}
        onSelect={onSelect}
        onNewChat={noop}
        onDelete={noop}
      />,
    );
    await user.click(screen.getByText("25-1 예산안 문의"));
    expect(onSelect).toHaveBeenCalledWith("s1");
  });

  it("calls onNewChat when the + 새 채팅 button is clicked", async () => {
    const user = userEvent.setup();
    const onNewChat = vi.fn();
    render(
      <SessionSidebar
        sessions={SESSIONS}
        activeSessionId={null}
        onSelect={noop}
        onNewChat={onNewChat}
        onDelete={noop}
      />,
    );
    await user.click(screen.getByText("새 채팅"));
    expect(onNewChat).toHaveBeenCalled();
  });
});
