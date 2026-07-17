// Raw text/event-stream framing parser — separate from the typed chat event
// mapping below so the line-splitting logic can be unit tested independent
// of chat.py's payload shapes (webapp-spec S4: "SSE 파서는 유틸 함수로 분리").
// 원시 text/event-stream 프레이밍 파서 — 아래 타입드 채팅 이벤트 매핑과 분리해,
// 줄 파싱 로직을 chat.py 페이로드 모양과 무관하게 단위 테스트할 수 있게 한다.

export interface RawSSEEvent {
  event: string;
  data: string;
}

interface ParseResult {
  events: RawSSEEvent[];
  remainder: string;
}

// Parses as many complete `\n\n`-terminated blocks as `buffer` contains and
// returns the leftover partial block for the caller to prepend to the next
// chunk. Comment lines (leading `:`) and blank lines outside a block are
// ignored per the SSE spec; repeated `data:` lines within one block join
// with `\n` (also per spec — sse_starlette never emits these, but a
// spec-faithful parser shouldn't assume that).
// `buffer`에 들어있는 만큼 `\n\n` 종결 블록을 전부 파싱하고, 나머지 미완성
// 블록은 다음 청크에 이어붙이도록 반환한다. 주석 줄(`:` 시작)과 블록 밖 빈
// 줄은 SSE 스펙대로 무시한다. 한 블록 안 반복된 `data:` 줄은 스펙대로 `\n`
// 조인한다(sse_starlette는 이렇게 안 보내지만, 스펙에 충실한 파서는 이를
// 가정하면 안 된다).
export function parseSSEChunk(buffer: string): ParseResult {
  const blocks = buffer.split("\n\n");
  const remainder = blocks.pop() ?? "";
  const events: RawSSEEvent[] = [];

  for (const block of blocks) {
    let event = "message";
    const dataLines: string[] = [];
    for (const rawLine of block.split("\n")) {
      const line = rawLine.replace(/\r$/, "");
      if (line === "" || line.startsWith(":")) continue;
      if (line.startsWith("event:")) {
        event = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
      }
    }
    if (dataLines.length > 0) {
      events.push({ event, data: dataLines.join("\n") });
    }
  }

  return { events, remainder };
}

// Two citation shapes since S26: document citations from cite.py (kind:"doc",
// but older persisted rows predate the field — absent kind means doc) and web
// citations from web_generate.py (kind:"web", title+url only).
// S26부터 인용은 두 형태: cite.py의 문서 인용(kind:"doc" — 다만 필드 도입 전
// 저장분은 kind가 없으므로, 없으면 doc으로 간주)과 web_generate.py의 웹 인용
// (kind:"web", title+url만).
export interface DocCitation {
  kind?: "doc";
  marker: number;
  source_file: string;
  locator: string;
  category: string;
  semester: string | null;
  snippet: string;
}

export interface WebCitation {
  kind: "web";
  title: string;
  url: string;
}

export type Citation = DocCitation | WebCitation;

// Mirrors api/app/routes/chat.py's event order exactly:
// session? -> status* -> route -> token* -> citations -> done, or error.
// api/app/routes/chat.py의 이벤트 순서를 그대로 반영:
// session? -> status* -> route -> token* -> citations -> done, 또는 error.
export type ChatSSEEvent =
  | { type: "session"; session_id: string }
  | { type: "status"; stage: string; label: string }
  | { type: "route"; route: string }
  | { type: "token"; text: string }
  | { type: "citations"; citations: Citation[] }
  | {
      type: "done";
      latency_ms: number;
      model_used: string;
      session_id: string;
      remaining: number;
      // Present only when the turn ended with a fallback offer (webapp-spec
      // S26 — currently the only value is "web_search").
      // 턴이 폴백 제안으로 끝났을 때만 존재 (webapp-spec S26 — 현재 유일한
      // 값은 "web_search").
      offer?: string;
    }
  | { type: "error"; error: { code: string; message: string } };

// Maps a raw SSE frame to the typed union above. Unknown event names are
// dropped (forward-compat with future backend event additions) rather than
// thrown, so a stream doesn't die on one unrecognized frame.
// 위 타입드 유니온으로 원시 SSE 프레임을 매핑한다. 모르는 이벤트 이름은
// (향후 백엔드가 이벤트를 추가해도 대비되도록) 예외 없이 버린다 — 스트림이
// 인식 못 하는 프레임 하나 때문에 죽지 않는다.
export function toChatSSEEvent(raw: RawSSEEvent): ChatSSEEvent | null {
  try {
    const data = JSON.parse(raw.data) as Record<string, unknown>;
    switch (raw.event) {
      case "session":
        return { type: "session", session_id: String(data.session_id) };
      case "status":
        return { type: "status", stage: String(data.stage), label: String(data.label) };
      case "route":
        return { type: "route", route: String(data.route) };
      case "token":
        return { type: "token", text: String(data.text) };
      case "citations":
        return { type: "citations", citations: (data.citations as Citation[]) ?? [] };
      case "done":
        return {
          type: "done",
          latency_ms: Number(data.latency_ms),
          model_used: String(data.model_used),
          session_id: String(data.session_id),
          remaining: Number(data.remaining),
          ...(typeof data.offer === "string" ? { offer: data.offer } : {}),
        };
      case "error":
        return { type: "error", error: data.error as { code: string; message: string } };
      default:
        return null;
    }
  } catch {
    return null;
  }
}

// Reads a fetch Response body as a sequence of typed chat events. Used by
// useChatStream (React hook) — kept as a plain async generator here so the
// stream-consumption logic itself is testable without React.
// fetch Response 바디를 타입드 채팅 이벤트 시퀀스로 읽는다. useChatStream(리액트
// 훅)이 사용 — 스트림 소비 로직 자체를 React 없이 테스트할 수 있도록 순수
// 비동기 제너레이터로 둔다.
export async function* readChatSSEStream(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatSSEEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, remainder } = parseSSEChunk(buffer);
      buffer = remainder;
      for (const raw of events) {
        const event = toChatSSEEvent(raw);
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
