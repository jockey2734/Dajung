"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { readChatSSEStream } from "@/lib/sse-parser";
import type { AttachmentChip, ChatMessage, Citation, FallbackMode, SessionSummary } from "@/lib/chat-types";
import { isPersistedMessageId } from "@/lib/chat-types";

// Mode turns skip router/rerank so no route event and no per-stage status
// updates arrive (webapp-spec S27 stream-contract note) — show one fixed
// label instead of the RAG stage labels.
// mode 턴은 router/rerank를 건너뛰어 route 이벤트도 단계별 status도 오지
// 않는다 (webapp-spec S27 스트림 계약 주의) — RAG 단계 라벨 대신 고정 라벨
// 하나를 보여준다.
const MODE_LABELS: Record<FallbackMode, string> = {
  web: "웹에서 검색하고 있어요",
  plain: "답변을 생성하고 있어요",
};

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
    my_feedback: -1 | 1 | null;
  }>;
}

function mapSessionMessages(messages: SessionDetailApiResponse["messages"]): ChatMessage[] {
  return messages.map((m) => ({
    id: m.id,
    role: m.role === "user" ? "user" : "assistant",
    content: m.content,
    status: "done",
    route: m.metadata.route,
    citations: m.metadata.citations,
    myFeedback: m.my_feedback,
  }));
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
    setMessages(mapSessionMessages(body.messages));
    setAttachments([]);
  }, []);

  // Fires after a stream's `done` event. The just-finished turn's messages
  // still carry client-only turn ids (nextTurnId) — this swaps the whole
  // list for the DB-backed rows (real ids, `my_feedback`) so feedback
  // buttons have something to PUT/DELETE against. Guarded by session id so a
  // user who already switched sessions before this resolves doesn't have
  // their new session's messages clobbered by a stale response.
  // 스트림 `done` 이벤트 후 실행된다. 방금 끝난 턴의 메시지는 아직 클라이언트
  // 전용 턴 id(nextTurnId)를 가지므로, DB 기반 행(실제 id·`my_feedback`)으로
  // 전체 목록을 교체해 피드백 버튼이 PUT/DELETE할 대상을 갖게 한다. 이 응답이
  // 오기 전에 사용자가 다른 세션으로 이동했다면 그 새 세션의 메시지를 stale
  // 응답이 덮어쓰지 않도록 세션 id로 가드한다.
  const refreshMessages = useCallback(async (sessionId: string) => {
    const res = await fetch(`/api/sessions/${sessionId}`);
    if (!res.ok) return;
    const body = (await res.json()) as SessionDetailApiResponse;
    if (activeSessionIdRef.current !== sessionId) return;
    setMessages((prev) => {
      const next = mapSessionMessages(body.messages);
      // The offer buttons are live-stream-only (webapp-spec S27), so
      // mapSessionMessages never restores `offer` from metadata — but this
      // internal id swap runs right after `done` and must not eat a
      // just-offered turn's buttons. Carry the live turn's offer state (and
      // its retryQuery, which holds the original question to resend) onto
      // the refreshed last assistant row.
      // 제안 버튼은 라이브 스트림 전용이라(webapp-spec S27)
      // mapSessionMessages는 metadata에서 `offer`를 복원하지 않는다 — 그런데
      // 이 내부 id 교체는 `done` 직후 실행되므로 방금 제안된 턴의 버튼을
      // 지워버리면 안 된다. 라이브 턴의 offer 상태(와 재전송할 원 질문이 든
      // retryQuery)를 새로고침된 마지막 assistant 행으로 옮긴다.
      const prevLast = prev[prev.length - 1];
      const nextLast = next[next.length - 1];
      if (prevLast?.role === "assistant" && prevLast.offer && nextLast?.role === "assistant") {
        next[next.length - 1] = {
          ...nextLast,
          offer: prevLast.offer,
          offerConsumed: prevLast.offerConsumed,
          retryQuery: prevLast.retryQuery,
        };
      }
      return next;
    });
  }, []);

  const patchMessageById = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
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
    async (text: string, attachmentIds: string[] = [], mode?: FallbackMode) => {
      const turnId = nextTurnId();
      const userMessageId = `${turnId}-user`;
      const assistantMessageId = `${turnId}-assistant`;

      setMessages((prev) => [
        ...prev,
        { id: userMessageId, role: "user", content: text, status: "done" },
        { id: assistantMessageId, role: "assistant", content: "", status: "streaming", retryQuery: text },
      ]);
      setRagLabel(mode ? MODE_LABELS[mode] : "질문을 분류하고 있어요");
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
            // Omitted for normal turns — the backend defaults to "rag".
            // 일반 턴에서는 생략 — 백엔드 기본값이 "rag"다.
            ...(mode ? { mode } : {}),
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
              // The `done` handler below reads this ref, and both events can
              // land in the same synchronous SSE-processing tick — mutate it
              // directly so a brand-new chat's first refreshMessages() guard
              // check isn't comparing against a stale (pre-render) null.
              // 아래 `done` 핸들러가 이 ref를 읽는데, 두 이벤트가 같은 동기
              // SSE 처리 틱 안에 올 수 있다 — 새 채팅 첫 턴의 refreshMessages()
              // 가드 체크가 (리렌더 전) stale한 null과 비교하지 않도록 직접
              // mutate한다.
              activeSessionIdRef.current = event.session_id;
              break;
            case "status":
              // Mode turns only ever get the generic "routing" status even
              // though they skip the router — keep the fixed mode label
              // instead (webapp-spec S27 "진행표시 간소화").
              // mode 턴은 router를 건너뛰는데도 범용 "routing" status만 오므로
              // 고정 mode 라벨을 유지한다 (webapp-spec S27 "진행표시 간소화").
              if (!mode) setRagLabel(event.label);
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
              patchAssistant({ status: "done", offer: event.offer });
              setRemaining(event.remaining);
              void loadSessions();
              void refreshMessages(event.session_id);
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
    [loadSessions, refreshMessages],
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

  // Offer button click (webapp-spec S27): resend the original question as a
  // brand-new turn with the picked mode, and mark the offer consumed so both
  // buttons disable immediately. Same read-inside-setMessages shape as
  // `retry` above — the functional update doubles as the double-click guard
  // (the second click sees offerConsumed already true and no-ops).
  // 제안 버튼 클릭 (webapp-spec S27): 원 질문을 선택한 mode의 완전한 새 턴으로
  // 재전송하고, offer를 소비 처리해 두 버튼을 즉시 비활성화한다. 위 `retry`와
  // 같은 setMessages 내부 읽기 형태 — 함수형 업데이트가 더블클릭 가드를 겸한다
  // (두 번째 클릭은 이미 true인 offerConsumed를 보고 아무것도 안 한다).
  const acceptOffer = useCallback(
    (messageId: string, mode: FallbackMode) => {
      setMessages((prev) => {
        const target = prev.find((m) => m.id === messageId);
        if (!target?.offer || target.offerConsumed || !target.retryQuery) return prev;
        void sendMessage(target.retryQuery, [], mode);
        return prev.map((m) => (m.id === messageId ? { ...m, offerConsumed: true } : m));
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

  // Same-button re-click clears the vote (DELETE); the other button swaps it
  // (PUT upsert, S13 handles the overwrite). Optimistic + rollback, same
  // shape as usePantry's updateItem (webapp-spec S14 "S5 pattern").
  // 같은 버튼 재클릭은 투표 취소(DELETE), 반대 버튼은 교체(PUT upsert, S13가
  // 덮어쓰기 처리). 낙관적 업데이트+롤백, usePantry의 updateItem과 동일한
  // 형태(webapp-spec S14 "S5 pattern").
  const setFeedback = useCallback(
    async (messageId: string, rating: -1 | 1) => {
      if (!isPersistedMessageId(messageId)) return;
      const previous = messages.find((m) => m.id === messageId)?.myFeedback ?? null;
      const next = previous === rating ? null : rating;
      patchMessageById(messageId, { myFeedback: next });

      try {
        const res =
          next === null
            ? await fetch(`/api/messages/${messageId}/feedback`, { method: "DELETE" })
            : await fetch(`/api/messages/${messageId}/feedback`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ rating: next }),
              });
        if (!res.ok) throw new Error("feedback update failed");
      } catch {
        patchMessageById(messageId, { myFeedback: previous });
      }
    },
    [messages, patchMessageById],
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
    setFeedback,
    acceptOffer,
  };
}
