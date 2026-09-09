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

describe("MessageList web-fallback offer buttons (webapp-spec S27)", () => {
  const offerMessage = () =>
    doneAssistant({
      content: "문서 검색에 실패했습니다. 웹 검색을 시도해보시겠습니까?",
      offer: "web_search",
      retryQuery: "원래 질문",
    });

  it("renders both offer buttons under a done message with offer web_search", () => {
    render(<MessageList messages={[offerMessage()]} onAcceptOffer={vi.fn()} />);
    expect(screen.getByRole("button", { name: "웹에서 검색" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "그냥 답변 받기" })).toBeEnabled();
  });

  it("hides offer buttons when the message carries no offer", () => {
    render(<MessageList messages={[doneAssistant()]} onAcceptOffer={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "웹에서 검색" })).not.toBeInTheDocument();
  });

  it("calls onAcceptOffer with the picked mode", async () => {
    const user = userEvent.setup();
    const onAcceptOffer = vi.fn();
    render(<MessageList messages={[offerMessage()]} onAcceptOffer={onAcceptOffer} />);

    await user.click(screen.getByRole("button", { name: "웹에서 검색" }));
    expect(onAcceptOffer).toHaveBeenCalledWith("real-id-1", "web");

    await user.click(screen.getByRole("button", { name: "그냥 답변 받기" }));
    expect(onAcceptOffer).toHaveBeenCalledWith("real-id-1", "plain");
  });

  it("disables both buttons once the offer is consumed", () => {
    render(
      <MessageList messages={[{ ...offerMessage(), offerConsumed: true }]} onAcceptOffer={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "웹에서 검색" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "그냥 답변 받기" })).toBeDisabled();
  });

  it("disables both buttons while another stream is in flight (offerLocked)", () => {
    render(<MessageList messages={[offerMessage()]} onAcceptOffer={vi.fn()} offerLocked />);
    expect(screen.getByRole("button", { name: "웹에서 검색" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "그냥 답변 받기" })).toBeDisabled();
  });
});

describe("MessageList web citations (webapp-spec S27)", () => {
  it("renders kind:web citations as external links with noopener", () => {
    render(
      <MessageList
        messages={[
          doneAssistant({
            content: "(웹 검색 결과 — 동아리 내부 자료 아님)\n웹 답변",
            citations: [
              { kind: "web", title: "다도 소개", url: "https://example.com/tea" },
              { kind: "web", title: "차 역사", url: "https://example.com/history" },
            ],
          }),
        ]}
      />,
    );
    const link = screen.getByRole("link", { name: "다도 소개" });
    expect(link).toHaveAttribute("href", "https://example.com/tea");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("link", { name: "차 역사" })).toBeInTheDocument();
  });

  it("treats citations without kind as doc items (backward compat)", () => {
    render(
      <MessageList
        messages={[
          doneAssistant({
            content: "근거 있는 답변 [1]",
            citations: [
              {
                marker: 1,
                source_file: "운영문서.md",
                locator: "3장",
                category: "지식",
                semester: null,
                snippet: "발췌",
              },
            ],
          }),
        ]}
      />,
    );
    // Doc badge renders as an inline [1] button, and no web link list appears.
    // doc 배지는 인라인 [1] 버튼으로 렌더되고, 웹 링크 리스트는 나오지 않는다.
    expect(screen.getByRole("button", { name: "[1]" })).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("MessageList message time (webapp-spec S29)", () => {
  it("renders createdAt as relative time inside <time dateTime> for user and assistant messages", () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const { container } = render(
      <MessageList
        messages={[
          { id: "u1", role: "user", content: "질문", status: "done", createdAt: fiveMinutesAgo },
          doneAssistant({ createdAt: fiveMinutesAgo }),
        ]}
        onFeedback={vi.fn()}
      />,
    );
    const times = container.querySelectorAll("time");
    expect(times).toHaveLength(2);
    for (const time of Array.from(times)) {
      expect(time).toHaveAttribute("dateTime", fiveMinutesAgo);
      expect(time).toHaveTextContent("5분 전");
    }
    // Assistant time shares the footer row with the feedback buttons.
    // assistant 시각은 피드백 버튼과 같은 푸터 줄에 있다.
    expect(screen.getByRole("button", { name: "좋아요" }).parentElement?.parentElement).toContainElement(
      times[1],
    );
  });

  it("renders no time when createdAt is absent (rows mapped before S29)", () => {
    const { container } = render(
      <MessageList
        messages={[{ id: "u1", role: "user", content: "질문", status: "done" }, doneAssistant()]}
        onFeedback={vi.fn()}
      />,
    );
    expect(container.querySelector("time")).toBeNull();
    // Feedback buttons still render on their own in the footer row.
    // 피드백 버튼은 푸터 줄에 단독으로 여전히 렌더된다.
    expect(screen.getByRole("button", { name: "좋아요" })).toBeInTheDocument();
  });
});
