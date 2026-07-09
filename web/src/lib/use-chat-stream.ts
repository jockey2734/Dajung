"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { readChatSSEStream } from "@/lib/sse-parser";
import type { AttachmentChip, ChatMessage, Citation, SessionSummary } from "@/lib/chat-types";

// Initial display before the first server `done.remaining` arrives.
// 첫 서버 `done.remaining` 값이 오기 전 초기 표시값.
const DAILY_CHAT_LIMIT = 20;

let turnCounter = 0;
function nextTurnId(): string {
  turnCounter += 1;
  return `turn-${Date.now()}-${turnCounter}`;
}

interface SessionListApiResponse {
  sessions: Array<{ id: string; title: string; last_message_at: string | null; message_count: number }>;
}

interface SessionDetailApiResponse {
  id: string;
  title: string;
  messages: Array<{
    id: string;
    role: string;
    content: string;
    metadata: { route?: string; citations?: Citation[] };
    created_at: string;
  }>;
}

interface UploadApiResponse {
  attachments: Array<{ id: string; name: string; chars: number; parse_status: "parsed" | "failed" }>;
}

export function useChatStream() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [ragLabel, setRagLabel] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<AttachmentChip[]>([]);
  const [remaining, setRemaining] = useState(DAILY_CHAT_LIMIT);
  const [isStreaming, setIsStreaming] = useState(false);
  // Lets sendMessage read the *latest* session id without depending on
  // (and being torn down/rebuilt by) activeSessionId — ChatComposer holds
  // onSend across renders via a stable callback identity.
  // sendMessage가 activeSessionId에 의존(해서 그때마다 재생성)하지 않고도
  // 최신 세션 id를 읽게 한다 — ChatComposer는 onSend를 안정적인 콜백
  // identity로 여러 렌더에 걸쳐 들고 있는다.
  const activeSessionIdRef = useRef<string | null>(null);
  activeSessionIdRef.current = activeSessionId;

  const loadSessions = useCallback(async () => {
    const res = await fetch("/api/sessions");
    if (!res.ok) return;
    const body = (await res.json()) as SessionListApiResponse;
    setSessions(
      body.sessions.map((s) => ({
        id: s.id,
        title: s.title,
        lastMessageAt: s.last_message_at,
        messageCount: s.message_count,
      })),
    );
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const newChat = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setAttachments([]);
  }, []);

  const selectSession = useCallback(async (id: string) => {
    const res = await fetch(`/api/sessions/${id}`);
    if (!res.ok) return;
    const body = (await res.json()) as SessionDetailApiResponse;
    setActiveSessionId(body.id);
    setMessages(
      body.messages.map((m) => ({
        id: m.id,
        role: m.role === "user" ? "user" : "assistant",
        content: m.content,
        status: "done",
        route: m.metadata.route,
        citations: m.metadata.citations,
      })),
    );
    setAttachments([]);
  }, []);

  const deleteSession = useCallback(
    async (id: string) => {
      const res = await fetch(`/api/sessions/${id}`, { method: "DELETE" });
      if (!res.ok) return;
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionIdRef.current === id) newChat();
    },
    [newChat],
  );

  const uploadFiles = useCallback(async (files: FileList) => {
    const form = new FormData();
    for (const file of Array.from(files)) form.append("files", file);
    const res = await fetch("/api/uploads", { method: "POST", body: form });
    if (!res.ok) return;
    const body = (await res.json()) as UploadApiResponse;
    setAttachments((prev) => [
      ...prev,
      ...body.attachments.map((a) => ({ id: a.id, name: a.name, chars: a.chars, parseStatus: a.parse_status })),
    ]);
  }, []);

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const sendMessage = useCallback(
    async (text: string, attachmentIds: string[] = []) => {
      const turnId = nextTurnId();
      const userMessageId = `${turnId}-user`;
      const assistantMessageId = `${turnId}-assistant`;

      setMessages((prev) => [
        ...prev,
        { id: userMessageId, role: "user", content: text, status: "done" },
        { id: assistantMessageId, role: "assistant", content: "", status: "streaming", retryQuery: text },
      ]);
      setRagLabel("질문을 분류하고 있어요");
      setIsStreaming(true);

      const patchAssistant = (patch: Partial<ChatMessage>) =>
        setMessages((prev) => prev.map((m) => (m.id === assistantMessageId ? { ...m, ...patch } : m)));

      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: text,
            session_id: activeSessionIdRef.current ?? undefined,
            attachment_ids: attachmentIds,
          }),
        });

        if (!res.body || !(res.headers.get("content-type") ?? "").includes("text/event-stream")) {
          const body = (await res.json().catch(() => null)) as { error?: { message?: string } } | null;
          throw new Error(body?.error?.message ?? "응답 생성 중 오류가 발생했습니다.");
        }

        for await (const event of readChatSSEStream(res.body)) {
          switch (event.type) {
            case "session":
              setActiveSessionId(event.session_id);
              break;
            case "status":
              setRagLabel(event.label);
              break;
            case "route":
              patchAssistant({ route: event.route });
              break;
            case "token":
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantMessageId ? { ...m, content: m.content + event.text } : m)),
              );
              break;
            case "citations":
              patchAssistant({ citations: event.citations });
              break;
            case "done":
              patchAssistant({ status: "done" });
              setRemaining(event.remaining);
              void loadSessions();
              break;
            case "error":
              patchAssistant({ status: "error", errorMessage: event.error.message });
              break;
          }
        }
      } catch (error) {
        patchAssistant({
          status: "error",
          errorMessage: error instanceof Error ? error.message : "응답 생성 중 오류가 발생했습니다.",
        });
      } finally {
        setRagLabel(null);
        setIsStreaming(false);
      }
    },
    [loadSessions],
  );

  // Attachments already linked to the failed user message can't be reused
  // (uploads.py: an Attachment with message_id set is rejected) — retry
  // resends the question text only, as a fresh turn.
  // 실패한 user 메시지에 이미 연결된 첨부는 재사용 불가(uploads.py: message_id
  // 설정된 Attachment는 거부) — retry는 질문 텍스트만 새 턴으로 재전송한다.
  const retry = useCallback(
    (messageId: string) => {
      setMessages((prev) => {
        const target = prev.find((m) => m.id === messageId);
        if (target?.retryQuery) void sendMessage(target.retryQuery);
        return prev;
      });
    },
    [sendMessage],
  );

  const sendWithAttachments = useCallback(
    (text: string) => {
      const ids = attachments.map((a) => a.id);
      setAttachments([]);
      void sendMessage(text, ids);
    },
    [attachments, sendMessage],
  );

  return {
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
    sendMessage: sendWithAttachments,
    retry,
  };
}
