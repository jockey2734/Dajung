"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Paperclip, Send, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AttachmentChip } from "@/lib/chat-types";

// webapp-plan §4.2: pdf/docx/xlsx/pptx/md/txt/image, matching
// api/app/routes/uploads.py's _ALLOWED_MIME exactly.
const ACCEPT = ".pdf,.docx,.pptx,.xlsx,.md,.txt,image/jpeg,image/png";

export function ChatComposer({
  attachments,
  onAttach,
  onRemoveAttachment,
  remaining,
  disabled,
  onSend,
  prefill,
}: {
  attachments: AttachmentChip[];
  onAttach: (files: FileList) => void;
  onRemoveAttachment: (id: string) => void;
  remaining: number;
  disabled?: boolean;
  onSend: (text: string) => void;
  // webapp-spec S12: example-card click fills the composer + focuses it
  // without sending. A fresh object reference per pick (even for repeated
  // text) is what re-triggers the effect below.
  prefill?: { text: string } | null;
}) {
  const [value, setValue] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!prefill) return;
    setValue(prefill.text);
    textareaRef.current?.focus();
  }, [prefill]);

  function handleSend() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col gap-2 border-t border-hairline-strong bg-canvas p-4">
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachments.map((attachment) => (
            <span
              key={attachment.id}
              className={cn(
                "flex items-center gap-1.5 rounded-md border border-hairline bg-surface px-2 py-1 text-caption text-mocha",
                attachment.parseStatus === "failed" && "border-semantic-error text-semantic-error",
              )}
            >
              {attachment.name}
              <button
                type="button"
                aria-label={`${attachment.name} 제거`}
                onClick={() => onRemoveAttachment(attachment.id)}
                className="text-taupe hover:text-ink"
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2 rounded-lg border border-hairline-strong bg-canvas p-3">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(event) => {
            if (event.target.files && event.target.files.length > 0) {
              onAttach(event.target.files);
            }
            event.target.value = "";
          }}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="파일 첨부"
          onClick={() => fileInputRef.current?.click()}
        >
          <Paperclip className="size-4" />
        </Button>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder="질문을 입력하세요"
          className="max-h-40 flex-1 resize-none bg-transparent text-body text-ink outline-none placeholder:text-taupe"
        />
        <Button type="button" size="icon" aria-label="전송" disabled={disabled || !value.trim()} onClick={handleSend}>
          <Send className="size-4" />
        </Button>
      </div>
      <p className="text-micro text-taupe">오늘 남은 질문 {remaining}회</p>
    </div>
  );
}
