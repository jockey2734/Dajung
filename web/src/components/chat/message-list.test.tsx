import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageList } from "./message-list";
import type { ChatMessage } from "@/lib/chat-types";

afterEach(() => {
  cleanup();
});

function doneAssistant(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "real-id-1",
    role: "assistant",
    content: "답변입니다",
    status: "done",
    myFeedback: null,
    ...overrides,
  };
}

describe("MessageList feedback buttons (webapp-spec S14)", () => {
  it("shows 👍/👎 for a done assistant message with a real id", () => {
    render(<MessageList messages={[doneAssistant()]} onFeedback={vi.fn()} />);
    expect(screen.getByRole("button", { name: "좋아요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "싫어요" })).toBeInTheDocument();
  });

  it("hides feedback buttons while streaming", () => {
    render(
      <MessageList
        messages={[doneAssistant({ status: "streaming", content: "아직 스트리밍 중" })]}
        onFeedback={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: "좋아요" })).not.toBeInTheDocument();
  });

  it("hides feedback buttons for a turn-local id not yet swapped for the real one", () => {
    render(<MessageList messages={[doneAssistant({ id: "turn-123-assistant" })]} onFeedback={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "좋아요" })).not.toBeInTheDocument();
  });

  it("hides feedback buttons when onFeedback is not provided", () => {
    render(<MessageList messages={[doneAssistant()]} />);
    expect(screen.queryByRole("button", { name: "좋아요" })).not.toBeInTheDocument();
  });

  it("calls onFeedback with 1 on thumbs-up click and -1 on thumbs-down click", async () => {
    const user = userEvent.setup();
    const onFeedback = vi.fn();
    render(<MessageList messages={[doneAssistant()]} onFeedback={onFeedback} />);

    await user.click(screen.getByRole("button", { name: "좋아요" }));
    expect(onFeedback).toHaveBeenCalledWith("real-id-1", 1);

    await user.click(screen.getByRole("button", { name: "싫어요" }));
    expect(onFeedback).toHaveBeenCalledWith("real-id-1", -1);
  });

  it("marks the active rating as pressed", () => {
    render(<MessageList messages={[doneAssistant({ myFeedback: 1 })]} onFeedback={vi.fn()} />);
    expect(screen.getByRole("button", { name: "좋아요" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "싫어요" })).toHaveAttribute("aria-pressed", "false");
  });
});
