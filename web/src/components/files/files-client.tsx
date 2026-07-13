"use client";

import { useMemo, useState } from "react";
import { FileText, LockKeyhole, RefreshCw, Search, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useFiles } from "@/lib/use-files";
import type { FileEntry } from "@/types/files";

const DOC_TYPE_LABELS: Record<string, string> = {
  budget: "예산",
  coffee_knowledge: "커피 지식",
  equipment: "도구",
  handover: "인수인계",
  knowledge: "지식",
  meeting: "회의",
  misc: "기타",
  tea_knowledge: "차 지식",
};

function docTypeLabel(docType: string) {
  return DOC_TYPE_LABELS[docType] ?? docType;
}

function RestrictedBadge() {
  return (
    <span
      aria-label="제한 자료"
      className="inline-flex h-6 items-center gap-1 rounded-full border border-hairline-strong bg-surface px-2 text-caption-bold text-mocha"
      title="제한 자료"
    >
      <LockKeyhole className="h-3 w-3" aria-hidden="true" />
      제한
    </span>
  );
}

function FileName({ file }: { file: FileEntry }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <FileText className="h-4 w-4 shrink-0 text-taupe" aria-hidden="true" />
      <span className="min-w-0 break-words font-medium text-ink">{file.source_file}</span>
      {file.restricted && <RestrictedBadge />}
    </div>
  );
}

function EmptyState({ hasSearch }: { hasSearch: boolean }) {
  return (
    <div className="rounded-md border border-hairline bg-canvas p-8 text-center text-body text-taupe">
      {hasSearch ? "검색 결과가 없습니다" : "인덱싱된 자료가 없습니다"}
    </div>
  );
}

function DeleteButton({ file, onDeleteRequest }: { file: FileEntry; onDeleteRequest: (file: FileEntry) => void }) {
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={`${file.source_file} 삭제`}
      className="text-taupe hover:text-semantic-error"
      onClick={() => onDeleteRequest(file)}
    >
      <Trash2 className="size-4" />
    </Button>
  );
}

function FilesTable({
  files,
  onDeleteRequest,
}: {
  files: FileEntry[];
  onDeleteRequest?: (file: FileEntry) => void;
}) {
  return (
    <div className="hidden w-full overflow-x-auto rounded-md border border-hairline bg-canvas md:block">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-hairline bg-surface text-caption-bold text-taupe">
            <th className="px-4 py-3">파일명</th>
            <th className="px-4 py-3">종류</th>
            <th className="px-4 py-3">학기</th>
            <th className="px-4 py-3 text-right">청크 수</th>
            {onDeleteRequest && <th className="px-4 py-3 w-12" />}
          </tr>
        </thead>
        <tbody className="text-body-sm">
          {files.map((file) => (
            <tr
              key={file.doc_id}
              className="border-b border-hairline transition-colors last:border-b-0 hover:bg-surface-soft/50"
            >
              <td className="max-w-[34rem] px-4 py-3">
                <FileName file={file} />
              </td>
              <td className="px-4 py-3 text-mocha">{docTypeLabel(file.doc_type)}</td>
              <td className="px-4 py-3 text-taupe">{file.semester ?? "-"}</td>
              <td className="px-4 py-3 text-right font-mono text-ink">{file.chunk_count}</td>
              {onDeleteRequest && (
                <td className="px-4 py-3 text-right">
                  <DeleteButton file={file} onDeleteRequest={onDeleteRequest} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FilesCardList({
  files,
  onDeleteRequest,
}: {
  files: FileEntry[];
  onDeleteRequest?: (file: FileEntry) => void;
}) {
  return (
    <div className="grid gap-3 md:hidden">
      {files.map((file) => (
        <article key={file.doc_id} className="rounded-md border border-hairline bg-canvas p-3 shadow-sm">
          <div className="flex items-start justify-between gap-2">
            <FileName file={file} />
            {onDeleteRequest && <DeleteButton file={file} onDeleteRequest={onDeleteRequest} />}
          </div>
          <dl className="mt-3 grid grid-cols-3 gap-2 text-caption">
            <div>
              <dt className="text-taupe">종류</dt>
              <dd className="mt-1 font-medium text-mocha">{docTypeLabel(file.doc_type)}</dd>
            </div>
            <div>
              <dt className="text-taupe">학기</dt>
              <dd className="mt-1 font-medium text-mocha">{file.semester ?? "-"}</dd>
            </div>
            <div>
              <dt className="text-taupe">청크</dt>
              <dd className="mt-1 font-mono font-medium text-ink">{file.chunk_count}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}

// Embedded mode (S21 admin docs tab) drops the page chrome, adds a refresh
// button (uploads index in the background — the list lags until re-fetched)
// and a per-row delete request hook. /files renders it with no props, so
// the staff-facing page is byte-for-byte the S9 behavior.
// embedded 모드(S21 관리자 문서 탭)는 페이지 크롬을 빼고 새로고침 버튼
// (업로드는 백그라운드 인덱싱 — 재조회 전까지 목록이 뒤처짐)과 행 단위 삭제
// 요청을 붙인다. /files는 prop 없이 렌더하므로 staff용 화면은 S9 동작
// 그대로다.
export function FilesClient({
  embedded = false,
  onDeleteRequest,
  reloadKey = 0,
}: {
  embedded?: boolean;
  onDeleteRequest?: (file: FileEntry) => void;
  reloadKey?: number;
} = {}) {
  const [internalReload, setInternalReload] = useState(0);
  const { files, loading, error } = useFiles(reloadKey + internalReload);
  const [query, setQuery] = useState("");

  const filteredFiles = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return [...files]
      .filter((file) => file.source_file.toLocaleLowerCase().includes(normalizedQuery))
      .sort((a, b) => a.source_file.localeCompare(b.source_file, "ko"));
  }, [files, query]);

  if (loading && files.length === 0) {
    return <div className="p-8 text-center text-taupe">로딩 중...</div>;
  }

  return (
    <div
      className={
        embedded
          ? "flex w-full flex-col gap-4"
          : "mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 pb-20 sm:p-6"
      }
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          {!embedded && (
            <h1 className="text-heading-2 font-semibold text-ink tracking-tight">자료 목록</h1>
          )}
          <p className={embedded ? "text-caption text-taupe" : "mt-1 text-caption text-taupe"}>
            {files.length}개 자료
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-taupe" />
            <Input
              aria-label="파일명 검색"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="파일명 검색"
              className="pl-8"
            />
          </div>
          {embedded && (
            <Button
              variant="ghost"
              size="icon"
              aria-label="목록 새로고침"
              onClick={() => setInternalReload((n) => n + 1)}
            >
              <RefreshCw className="size-4" />
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md border border-semantic-error/20 bg-semantic-error-soft p-3 text-sm text-semantic-error"
        >
          {error}
        </div>
      )}

      {!error && filteredFiles.length === 0 ? (
        <EmptyState hasSearch={query.trim().length > 0} />
      ) : (
        !error && (
          <>
            <FilesTable files={filteredFiles} onDeleteRequest={onDeleteRequest} />
            <FilesCardList files={filteredFiles} onDeleteRequest={onDeleteRequest} />
          </>
        )
      )}
    </div>
  );
}
