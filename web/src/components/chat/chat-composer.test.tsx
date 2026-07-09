import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatComposer } from "./chat-composer";

afterEach(() => {
  cleanup();
});

const noop = () => {};

describe("ChatComposer", () => {
  it("shows the daily remaining count (webapp-spec S4: 남은 일일 횟수 표시)", () => {
    render(
      <ChatComposer attachments={[]} onAttach={noop} onRemoveAttachment={noop} remaining={7} onSend={noop} />,
    );
    expect(screen.getByText("오늘 남은 질문 7회")).toBeInTheDocument();
  });

  it("sends trimmed text and clears the input on Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <ChatComposer attachments={[]} onAttach={noop} onRemoveAttachment={noop} remaining={20} onSend={onSend} />,
    );
    const textarea = screen.getByPlaceholderText("질문을 입력하세요");
    await user.type(textarea, "  안녕하세요  {enter}");
    expect(onSend).toHaveBeenCalledWith("안녕하세요");
    expect(textarea).toHaveValue("");
  });

  it("does not send on Shift+Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <ChatComposer attachments={[]} onAttach={noop} onRemoveAttachment={noop} remaining={20} onSend={onSend} />,
    );
    const textarea = screen.getByPlaceholderText("질문을 입력하세요");
    await user.type(textarea, "첫줄{Shift>}{enter}{/Shift}둘째줄");
    expect(onSend).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("첫줄\n둘째줄");
  });

  it("renders attachment chips and removes one on X click", async () => {
    const user = userEvent.setup();
    const onRemoveAttachment = vi.fn();
    render(
      <ChatComposer
        attachments={[{ id: "a1", name: "handover.pdf", chars: 500, parseStatus: "parsed" }]}
        onAttach={noop}
        onRemoveAttachment={onRemoveAttachment}
        remaining={20}
        onSend={noop}
      />,
    );
    expect(screen.getByText("handover.pdf")).toBeInTheDocument();
    await user.click(screen.getByLabelText("handover.pdf 제거"));
    expect(onRemoveAttachment).toHaveBeenCalledWith("a1");
  });

  it("disables the send button while streaming (disabled prop)", () => {
    render(
      <ChatComposer
        attachments={[]}
        onAttach={noop}
        onRemoveAttachment={noop}
        remaining={20}
        disabled
        onSend={noop}
      />,
    );
    expect(screen.getByLabelText("전송")).toBeDisabled();
  });
});
