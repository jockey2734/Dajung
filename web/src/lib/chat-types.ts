import type { Citation } from "@/lib/sse-parser";

export type { Citation };

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
