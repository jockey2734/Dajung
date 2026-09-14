import type { Citation, DocCitation, WebCitation } from "@/lib/sse-parser";

export type { Citation, DocCitation, WebCitation };

// Explicit-consent fallback modes for the offer buttons (webapp-spec S26/S27).
// "rag" is the request default, so it never needs sending from here.
// 제안 버튼의 명시적 동의 폴백 모드 (webapp-spec S26/S27). "rag"는 요청
// 기본값이라 여기서 보낼 일이 없다.
export type FallbackMode = "web" | "plain";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  // "streaming": tokens still arriving. "error": SSE `error` event replaced
  // this turn's bubble with an error card (webapp-spec S4).
  // "streaming": 토큰 수신 중. "error": SSE `error` 이벤트로 이 턴의 말풍선이
  // 에러 카드로 교체됨 (webapp-spec S4).
  status: "streaming" | "done" | "error";
  route?: string;
  citations?: Citation[];
  errorMessage?: string;
  // Assistant messages only — the paired user question, kept for onRetry.
  // Attachments already sent can't be reattached (uploads.py rejects an
  // Attachment once its message_id is set), so retry resends text only.
  // assistant 메시지 전용 — onRetry용으로 보관하는 짝지어진 질문. 이미 전송된
  // 첨부는 재첨부 불가(uploads.py가 message_id 설정된 Attachment를 거부)해,
  // retry는 텍스트만 재전송한다.
  retryQuery?: string;
  // Current user's 👍/👎 on this assistant message (webapp-spec S14). null =
  // no feedback yet; undefined only until the first session load/refresh.
  // 이 어시스턴트 메시지에 대한 현재 사용자의 👍/👎 (webapp-spec S14). null =
  // 아직 피드백 없음, undefined는 최초 세션 로드/새로고침 전까지만.
  myFeedback?: -1 | 1 | null;
  // done.offer from the live stream (webapp-spec S27) — set only on the turn
  // that just streamed, never restored from session metadata (buttons are
  // live-stream-only; after a reload the user re-asks).
  // 라이브 스트림의 done.offer (webapp-spec S27) — 방금 스트리밍된 턴에만
  // 설정되고 세션 metadata에서 복원하지 않는다 (버튼은 라이브 스트림 전용,
  // 새로고침 후엔 재질문).
  offer?: string;
  // True once either offer button was clicked — keeps both disabled.
  // 제안 버튼 중 하나를 클릭한 뒤 true — 두 버튼 모두 비활성 유지.
  offerConsumed?: boolean;
  // Millisecond-precision ISO 8601 — `MessageOut.created_at` re-serialized for
  // loaded rows, client clock for a just-streamed turn (webapp-spec S29).
  // Undefined only when the server value failed to parse; nothing renders then.
  // 밀리초 정밀도 ISO 8601 — 로드된 행은 `MessageOut.created_at` 재직렬화, 방금
  // 스트리밍된 턴은 클라이언트 시각 (webapp-spec S29). 서버 값 해석 실패 시에만
  // undefined이며 그땐 아무것도 렌더하지 않는다.
  createdAt?: string;
}

// A just-streamed message carries a client-only turn id (see nextTurnId in
// use-chat-stream.ts) until the post-`done` session refresh swaps in the
// real DB id. Feedback needs the real id, so gate the buttons on this.
// 방금 스트리밍된 메시지는 `done` 후 세션 새로고침이 실제 DB id로 바꿔주기
// 전까지 클라이언트 전용 턴 id를 가진다(use-chat-stream.ts의 nextTurnId 참고).
// 피드백은 실제 id가 필요하므로 버튼 노출을 이걸로 막는다.
export function isPersistedMessageId(id: string): boolean {
  return !id.startsWith("turn-");
}

export interface AttachmentChip {
  id: string;
  name: string;
  chars: number;
  parseStatus: "parsed" | "failed";
}

export interface SessionSummary {
  id: string;
  title: string;
  lastMessageAt: string | null;
  messageCount: number;
}
