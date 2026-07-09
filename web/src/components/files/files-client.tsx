"use client";

import { useMemo, useState } from "react";
import { FileText, LockKeyhole, Search } from "lucide-react";

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

function FilesTable({ files }: { files: FileEntry[] }) {
  return (
    <div className="hidden w-full overflow-x-auto rounded-md border border-hairline bg-canvas md:block">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-hairline bg-surface text-caption-bold text-taupe">
            <th className="px-4 py-3">파일명</th>
            <th className="px-4 py-3">종류</th>
            <th className="px-4 py-3">학기</th>
            <th className="px-4 py-3 text-right">청크 수</th>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FilesCardList({ files }: { files: FileEntry[] }) {
  return (
    <div className="grid gap-3 md:hidden">
      {files.map((file) => (
        <article key={file.doc_id} className="rounded-md border border-hairline bg-canvas p-3 shadow-sm">
          <FileName file={file} />
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

export function FilesClient() {
  const { files, loading, error } = useFiles();
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
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 pb-20 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-heading-2 font-semibold text-ink tracking-tight">자료 목록</h1>
          <p className="mt-1 text-caption text-taupe">{files.length}개 자료</p>
        </div>
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
            <FilesTable files={filteredFiles} />
            <FilesCardList files={filteredFiles} />
          </>
        )
      )}
    </div>
  );
}
