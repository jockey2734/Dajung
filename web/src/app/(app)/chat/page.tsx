"use client";

import { useEffect, useRef, useState } from "react";
import { SessionSidebar } from "@/components/chat/session-sidebar";
import { MessageList } from "@/components/chat/message-list";
import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatEmptyState } from "@/components/chat/chat-empty-state";
import { useChatStream } from "@/lib/use-chat-stream";

export default function ChatPage() {
  const {
    sessions,
    activeSessionId,
    messages,
    ragLabel,
    attachments,
    remaining,
    isStreaming,
    selectSession,
    newChat,
    deleteSession,
    uploadFiles,
    removeAttachment,
    sendMessage,
    retry,
  } = useChatStream();

  const [isDragging, setIsDragging] = useState(false);
  const [prefill, setPrefill] = useState<{ text: string } | null>(null);
  const dragDepth = useRef(0);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  function handleDragEnter(event: React.DragEvent) {
    event.preventDefault();
    dragDepth.current += 1;
    if (event.dataTransfer.types.includes("Files")) setIsDragging(true);
  }

  function handleDragLeave(event: React.DragEvent) {
    event.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setIsDragging(false);
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);
    if (event.dataTransfer.files.length > 0) void uploadFiles(event.dataTransfer.files);
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={(id) => void selectSession(id)}
        onNewChat={newChat}
        onDelete={(id) => void deleteSession(id)}
      />
      <div
        className="relative flex flex-1 flex-col"
        onDragEnter={handleDragEnter}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDragging && (
          <div className="absolute inset-2 z-10 flex items-center justify-center rounded-lg border-[1.5px] border-dashed border-primary bg-primary-soft/80 text-body-lg text-ink">
            파일을 여기에 놓으세요
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {messages.length === 0 ? (
            <ChatEmptyState
              show={messages.length === 0 && !isStreaming}
              onPickExample={(text) => setPrefill({ text })}
            />
          ) : (
            <MessageList messages={messages} ragLabel={ragLabel} onRetry={retry} />
          )}
          <div ref={scrollAnchorRef} />
        </div>
        <ChatComposer
          attachments={attachments}
          onAttach={(files) => void uploadFiles(files)}
          onRemoveAttachment={removeAttachment}
          remaining={remaining}
          disabled={isStreaming}
          onSend={sendMessage}
          prefill={prefill}
        />
      </div>
    </div>
  );
}
