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
