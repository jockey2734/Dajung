"use client";

import { useCallback, useEffect, useState } from "react";

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

// `externalReloadKey` lets a parent (S21's docs tab) force a reload after a
// delete or to pick up a background-ingested upload; /files never passes it.
// `externalReloadKey`로 부모(S21 문서 탭)가 삭제 후·백그라운드 인덱싱 반영용
// 재조회를 강제할 수 있다. /files는 넘기지 않는다.
export function useFiles(externalReloadKey = 0) {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadCount, setReloadCount] = useState(0);

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
  }, [reloadCount, externalReloadKey]);

  const refetch = useCallback(() => setReloadCount((n) => n + 1), []);

  return { files, loading, error, refetch };
}
