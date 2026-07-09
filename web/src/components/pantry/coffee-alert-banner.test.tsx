import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CoffeeAlertBanner } from "./coffee-alert-banner";

describe("CoffeeAlertBanner", () => {
  beforeEach(() => {
    vi.stubGlobal("sessionStorage", {
      getItem: vi.fn(),
      setItem: vi.fn(),
    });
  });

  it("should not render if alert is false", () => {
    const { container } = render(<CoffeeAlertBanner alert={{ alert: false, total_estimated_g: 600, threshold_g: 500 }} />);
    expect(container.firstChild).toBeNull();
  });

  it("should not render if alert is null", () => {
    const { container } = render(<CoffeeAlertBanner alert={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("should render if alert is true and show total_estimated_g", () => {
    render(<CoffeeAlertBanner alert={{ alert: true, total_estimated_g: 450, threshold_g: 500 }} />);
    expect(screen.getByText(/450g — 보충이 필요합니다/)).toBeDefined();
  });

  it("should not render if dismissed in sessionStorage", () => {
    vi.mocked(sessionStorage.getItem).mockReturnValue("true");
    const { container } = render(<CoffeeAlertBanner alert={{ alert: true, total_estimated_g: 450, threshold_g: 500 }} />);
    expect(container.firstChild).toBeNull();
  });

  it("should dismiss when close button is clicked", () => {
    render(<CoffeeAlertBanner alert={{ alert: true, total_estimated_g: 450, threshold_g: 500 }} />);
    const closeBtn = screen.getByRole("button", { name: "닫기" });
    
    fireEvent.click(closeBtn);
    
    expect(sessionStorage.setItem).toHaveBeenCalledWith("dajung.pantry.alert.dismissed", "true");
    expect(screen.queryByText(/보충이 필요합니다/)).toBeNull(); // Re-rendered and hidden
  });
});
