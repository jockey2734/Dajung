"use client";

import { useEffect, useState } from "react";

import type { FileEntry, FileListResponse } from "@/types/files";

const GENERIC_ERROR_MESSAGE = "자료 목록을 불러오지 못했습니다.";
const QDRANT_ERROR_MESSAGE = "검색 시스템에 연결할 수 없습니다.";

async function apiErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as {
      error?: { code?: string; message?: string };
    };
    if (data.error?.code === "qdrant_down") return QDRANT_ERROR_MESSAGE;
    return data.error?.message ?? GENERIC_ERROR_MESSAGE;
  } catch {
    return response.status === 503 ? QDRANT_ERROR_MESSAGE : GENERIC_ERROR_MESSAGE;
  }
}

export function useFiles() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function fetchFiles() {
      try {
        setLoading(true);
        const response = await fetch("/api/files");
        if (!response.ok) {
          throw new Error(await apiErrorMessage(response));
        }

        const data = (await response.json()) as FileListResponse;
        if (!ignore) {
          setFiles(data.files);
          setError(null);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : GENERIC_ERROR_MESSAGE);
          setFiles([]);
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void fetchFiles();

    return () => {
      ignore = true;
    };
  }, []);

  return { files, loading, error };
}
