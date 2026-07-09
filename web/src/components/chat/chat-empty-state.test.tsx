import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatEmptyState } from "./chat-empty-state";

afterEach(() => {
  cleanup();
});

describe("ChatEmptyState (webapp-spec S12)", () => {
  it("renders 3 example cards when show is true", () => {
    render(<ChatEmptyState show onPickExample={vi.fn()} />);
    expect(screen.getByText("에스프레소 그라인더 청소는 얼마나 자주 해요?")).toBeInTheDocument();
    expect(screen.getByText("총무 인수인계 때 계좌·비품 뭘 넘겨야 해요?")).toBeInTheDocument();
    expect(screen.getByText("다정은 어떤 동아리예요?")).toBeInTheDocument();
  });

  it("calls onPickExample with the card's question text on click", async () => {
    const user = userEvent.setup();
    const onPickExample = vi.fn();
    render(<ChatEmptyState show onPickExample={onPickExample} />);
    await user.click(screen.getByText("다정은 어떤 동아리예요?"));
    expect(onPickExample).toHaveBeenCalledWith("다정은 어떤 동아리예요?");
  });

  it("renders nothing when show is false", () => {
    const { container } = render(<ChatEmptyState show={false} onPickExample={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
