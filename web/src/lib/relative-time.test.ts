import { describe, expect, it } from "vitest";
import { formatRelativeTime } from "./relative-time";

const NOW = new Date("2026-07-09T12:00:00+09:00");

describe("formatRelativeTime", () => {
  it("shows 방금 under a minute", () => {
    expect(formatRelativeTime(new Date(NOW.getTime() - 30_000), NOW)).toBe("방금");
  });

  it("shows minutes under an hour", () => {
    expect(formatRelativeTime(new Date(NOW.getTime() - 5 * 60_000), NOW)).toBe("5분 전");
  });

  it("shows hours under a day", () => {
    expect(formatRelativeTime(new Date(NOW.getTime() - 3 * 3_600_000), NOW)).toBe("3시간 전");
  });

  it("shows days under a week", () => {
    expect(formatRelativeTime(new Date(NOW.getTime() - 2 * 86_400_000), NOW)).toBe("2일 전");
  });

  it("shows month/day within the same year past a week", () => {
    expect(formatRelativeTime(new Date("2026-07-01T12:00:00+09:00"), NOW)).toBe("7월 1일");
  });

  it("shows year.month.day for a different year", () => {
    expect(formatRelativeTime(new Date("2025-12-25T12:00:00+09:00"), NOW)).toBe("2025.12.25");
  });

  it("accepts an ISO string as input", () => {
    expect(formatRelativeTime("2026-07-09T11:59:30+09:00", NOW)).toBe("방금");
  });
});
