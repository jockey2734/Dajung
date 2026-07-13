import { describe, expect, it } from "vitest";
import { currentSemester, isPastSemester, nextSemester } from "./semester";

describe("semester helpers (webapp-spec S19/S21 KST term math)", () => {
  it("maps KST dates to terms — Jan/Feb belong to the previous year's term 2", () => {
    expect(currentSemester(new Date("2026-07-13T00:00:00+09:00"))).toBe("2026-1");
    expect(currentSemester(new Date("2026-09-01T00:00:00+09:00"))).toBe("2026-2");
    expect(currentSemester(new Date("2026-02-28T23:00:00+09:00"))).toBe("2025-2");
    // KST rollover: still Feb in UTC but already Mar 1 in Seoul.
    // KST 경계: UTC로는 2월이지만 서울은 이미 3/1.
    expect(currentSemester(new Date("2026-02-28T16:00:00Z"))).toBe("2026-1");
  });

  it("orders semesters chronologically as plain strings", () => {
    const now = new Date("2026-07-13T00:00:00+09:00");
    expect(isPastSemester("2025-2", now)).toBe(true);
    expect(isPastSemester("2026-1", now)).toBe(false);
    expect(isPastSemester("2026-2", now)).toBe(false);
  });

  it("advances 1→2 within a year and 2→next year's 1", () => {
    expect(nextSemester("2026-1")).toBe("2026-2");
    expect(nextSemester("2026-2")).toBe("2027-1");
  });
});
