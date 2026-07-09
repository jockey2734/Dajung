import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, renderHook, waitFor } from "@testing-library/react";

import { useFiles } from "./use-files";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("useFiles", () => {
  it("loads indexed files from the BFF files endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        files: [
          {
            doc_id: "doc-1",
            source_file: "예산안.xlsx",
            doc_type: "budget",
            semester: "2026-1",
            restricted: true,
            chunk_count: 3,
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useFiles());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetchMock).toHaveBeenCalledWith("/api/files");
    expect(result.current.files).toHaveLength(1);
    expect(result.current.files[0].source_file).toBe("예산안.xlsx");
    expect(result.current.error).toBeNull();
  });

  it("maps qdrant_down to the Korean search-system error", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        error: {
          code: "qdrant_down",
          message: "검색 시스템에 연결할 수 없습니다.",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useFiles());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.files).toEqual([]);
    expect(result.current.error).toBe("검색 시스템에 연결할 수 없습니다.");
  });
});
