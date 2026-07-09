import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePantry } from "./use-pantry";
import type { PantryItemOut } from "@/types/pantry";

const mockItem: PantryItemOut = {
  id: "1",
  name: "test coffee",
  kind: "coffee",
  remaining_pct: 100,
  capacity_g: 200,
  estimated_g: 200,
  note: null,
  updated_by: { id: "u1", name: "User" },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("usePantry", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("should optimistic update and rollback on failure", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    // 1. Initial fetch
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [mockItem], coffee_alert: { alert: false, total_estimated_g: 200, threshold_g: 500 } }),
    });

    const { result } = renderHook(() => usePantry());

    // Wait for initial load
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.items[0].remaining_pct).toBe(100);

    // 2. Setup patch failure
    fetchMock.mockRejectedValueOnce(new Error("Network failure"));

    // 3. Trigger update
    let error: unknown;
    await act(async () => {
      try {
        await result.current.updateItem("1", { remaining_pct: 50 });
      } catch (err) {
        error = err;
      }
    });

    // It should have failed
    expect(error).toBeDefined();

    // It should have rolled back to 100%
    expect(result.current.items[0].remaining_pct).toBe(100);
  });
});
