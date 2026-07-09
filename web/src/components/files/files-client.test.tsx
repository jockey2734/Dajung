import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { useFiles } from "@/lib/use-files";
import type { FileEntry } from "@/types/files";

import { FilesClient } from "./files-client";

vi.mock("@/lib/use-files", () => ({
  useFiles: vi.fn(),
}));

const mockUseFiles = vi.mocked(useFiles);

const FILES: FileEntry[] = [
  {
    doc_id: "doc-1",
    source_file: "예산안.xlsx",
    doc_type: "budget",
    semester: "2026-1",
    restricted: true,
    chunk_count: 3,
  },
  {
    doc_id: "doc-2",
    source_file: "운영 가이드.md",
    doc_type: "unknown_type",
    semester: null,
    restricted: false,
    chunk_count: 8,
  },
];

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("FilesClient", () => {
  it("filters the read-only list by source filename", async () => {
    const user = userEvent.setup();
    mockUseFiles.mockReturnValue({ files: FILES, loading: false, error: null });

    render(<FilesClient />);

    expect(screen.getAllByText("예산안.xlsx").length).toBeGreaterThan(0);
    expect(screen.getAllByText("운영 가이드.md").length).toBeGreaterThan(0);

    await user.type(screen.getByLabelText("파일명 검색"), "예산");

    expect(screen.getAllByText("예산안.xlsx").length).toBeGreaterThan(0);
    expect(screen.queryByText("운영 가이드.md")).toBeNull();
    expect(screen.getAllByText("제한").length).toBeGreaterThan(0);
  });

  it("renders the empty indexed-files message", () => {
    mockUseFiles.mockReturnValue({ files: [], loading: false, error: null });

    render(<FilesClient />);

    expect(screen.getByText("인덱싱된 자료가 없습니다")).toBeInTheDocument();
  });
});
