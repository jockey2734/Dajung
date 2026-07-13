"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FilesClient } from "@/components/files/files-client";
import { useAdminDocs } from "@/lib/use-admin-tabs";
import type { FileEntry } from "@/types/files";

const ACTION_ERROR_FALLBACK = "요청을 처리하지 못했습니다.";

// Mirrors api/app/documents.py ALLOWED_DOCUMENT_EXTENSIONS.
// api/app/documents.py ALLOWED_DOCUMENT_EXTENSIONS를 반영.
const ACCEPT_EXTENSIONS = ".md,.txt,.csv,.pdf,.docx,.xlsx,.pptx";

export function DocsTab() {
  const { folders, upload, removeDocument } = useAdminDocs();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [folder, setFolder] = useState("");
  const [file, setFile] = useState<File | null>(null);
  // Uploads ingest in the background (202) — the /files list won't show them
  // until indexing finishes, so recent uploads are tracked here as chips.
  // 업로드는 백그라운드 인덱싱(202) — 인덱싱이 끝나기 전엔 /files 목록에 안
  // 보이므로 최근 업로드를 여기서 칩으로 표시한다.
  const [processing, setProcessing] = useState<string[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<FileEntry | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function resetUploadDialog(nextOpen: boolean) {
    setUploadOpen(nextOpen);
    setActionError(null);
    if (nextOpen) {
      setFolder("");
      setFile(null);
    }
  }

  async function handleUpload() {
    if (!folder || !file || busy) return;
    setBusy(true);
    setActionError(null);
    try {
      const result = await upload(folder, file);
      setProcessing((prev) => [...prev, `${result.folder}/${result.filename}`]);
      resetUploadDialog(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button onClick={() => resetUploadDialog(true)}>문서 업로드</Button>
      </div>

      {processing.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-hairline bg-surface p-3">
          <Loader2 className="size-4 animate-spin text-taupe" aria-hidden />
          <span className="text-body-sm text-taupe">인덱싱 처리 중 — 완료 후 목록 새로고침:</span>
          {processing.map((name) => (
            <span
              key={name}
              className="rounded-full border border-hairline bg-canvas px-2 py-0.5 text-caption text-mocha"
            >
              {name}
            </span>
          ))}
        </div>
      )}

      <FilesClient
        embedded
        reloadKey={reloadKey}
        onDeleteRequest={(target) => {
          setActionError(null);
          setDeleteTarget(target);
        }}
      />

      <Dialog open={uploadOpen} onOpenChange={resetUploadDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>문서 업로드</DialogTitle>
            <DialogDescription>
              업로드된 문서는 백그라운드에서 인덱싱되어 검색에 반영됩니다.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="docs-folder">폴더</Label>
              <select
                id="docs-folder"
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">폴더 선택</option>
                {folders.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              {folders.length === 0 && (
                <p className="text-caption text-taupe">
                  업로드 가능한 폴더를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="docs-file">파일</Label>
              <input
                id="docs-file"
                type="file"
                accept={ACCEPT_EXTENSIONS}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-body-sm text-ink file:mr-3 file:rounded-md file:border file:border-input file:bg-background file:px-3 file:py-1.5 file:text-sm"
              />
            </div>
            {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => resetUploadDialog(false)}>
              취소
            </Button>
            <Button disabled={!folder || !file || busy} onClick={handleUpload}>
              업로드
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>문서 삭제 — {deleteTarget?.source_file}</DialogTitle>
            <DialogDescription>
              인덱스에서 제거되고 원본은 휴지통으로 이동합니다.
            </DialogDescription>
          </DialogHeader>
          {actionError && <p className="text-body-sm text-semantic-error">{actionError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              취소
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setActionError(null);
                try {
                  await removeDocument(deleteTarget!.doc_id);
                  setDeleteTarget(null);
                  setReloadKey((n) => n + 1);
                } catch (err) {
                  setActionError(err instanceof Error ? err.message : ACTION_ERROR_FALLBACK);
                } finally {
                  setBusy(false);
                }
              }}
            >
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
