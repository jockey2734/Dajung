import { describe, expect, it } from "vitest";
import { parseSSEChunk, readChatSSEStream, toChatSSEEvent } from "./sse-parser";

describe("parseSSEChunk", () => {
  it("parses a single complete event", () => {
    const { events, remainder } = parseSSEChunk('event: route\ndata: {"route":"knowledge_query"}\n\n');
    expect(events).toEqual([{ event: "route", data: '{"route":"knowledge_query"}' }]);
    expect(remainder).toBe("");
  });

  it("parses multiple events in one buffer", () => {
    const buffer =
      'event: status\ndata: {"stage":"routing","label":"a"}\n\n' +
      'event: token\ndata: {"text":"hi"}\n\n';
    const { events, remainder } = parseSSEChunk(buffer);
    expect(events).toHaveLength(2);
    expect(events[0].event).toBe("status");
    expect(events[1].event).toBe("token");
    expect(remainder).toBe("");
  });

  it("holds back an incomplete trailing block for the next chunk", () => {
    const { events, remainder } = parseSSEChunk('event: token\ndata: {"text":"hi"}\n\nevent: token\ndata: {"tex');
    expect(events).toEqual([{ event: "token", data: '{"text":"hi"}' }]);
    expect(remainder).toBe('event: token\ndata: {"tex');
  });

  it("reassembles an event split mid-line across two chunks", () => {
    const first = parseSSEChunk('event: token\ndata: {"tex');
    expect(first.events).toEqual([]);
    const second = parseSSEChunk(first.remainder + 't":"hi"}\n\n');
    expect(second.events).toEqual([{ event: "token", data: '{"text":"hi"}' }]);
  });

  it("joins repeated data: lines within one block with a newline", () => {
    const { events } = parseSSEChunk("event: token\ndata: line1\ndata: line2\n\n");
    expect(events[0].data).toBe("line1\nline2");
  });

  it("ignores comment lines and defaults event to 'message' when unnamed", () => {
    const { events } = parseSSEChunk(':heartbeat\ndata: {"x":1}\n\n');
    expect(events).toEqual([{ event: "message", data: '{"x":1}' }]);
  });

  it("drops blocks with no data: line", () => {
    const { events } = parseSSEChunk("event: ping\n\n");
    expect(events).toEqual([]);
  });
});

describe("toChatSSEEvent", () => {
  it("maps every backend event name (api/app/routes/chat.py order)", () => {
    expect(toChatSSEEvent({ event: "session", data: '{"session_id":"s1"}' })).toEqual({
      type: "session",
      session_id: "s1",
    });
    expect(toChatSSEEvent({ event: "status", data: '{"stage":"retrieving","label":"자료를 검색하고 있어요"}' })).toEqual({
      type: "status",
      stage: "retrieving",
      label: "자료를 검색하고 있어요",
    });
    expect(toChatSSEEvent({ event: "route", data: '{"route":"handover_query"}' })).toEqual({
      type: "route",
      route: "handover_query",
    });
    expect(toChatSSEEvent({ event: "token", data: '{"text":"안녕"}' })).toEqual({
      type: "token",
      text: "안녕",
    });
    expect(
      toChatSSEEvent({
        event: "citations",
        data: '{"citations":[{"marker":1,"source_file":"a.pdf","locator":"p.3","category":"handover","semester":"2025-2","snippet":"..."}]}',
      }),
    ).toEqual({
      type: "citations",
      citations: [
        { marker: 1, source_file: "a.pdf", locator: "p.3", category: "handover", semester: "2025-2", snippet: "..." },
      ],
    });
    expect(
      toChatSSEEvent({ event: "done", data: '{"latency_ms":120,"model_used":"claude-haiku-4-5","session_id":"s1"}' }),
    ).toEqual({ type: "done", latency_ms: 120, model_used: "claude-haiku-4-5", session_id: "s1" });
    expect(
      toChatSSEEvent({ event: "error", data: '{"error":{"code":"llm_down","message":"응답 생성 중 오류가 발생했습니다."}}' }),
    ).toEqual({ type: "error", error: { code: "llm_down", message: "응답 생성 중 오류가 발생했습니다." } });
  });

  it("returns null for an unknown event name instead of throwing", () => {
    expect(toChatSSEEvent({ event: "future_event", data: "{}" })).toBeNull();
  });

  it("returns null for malformed JSON instead of throwing", () => {
    expect(toChatSSEEvent({ event: "token", data: "{not json" })).toBeNull();
  });
});

describe("readChatSSEStream", () => {
  function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
    const encoder = new TextEncoder();
    return new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });
  }

  it("yields typed events across a stream split at arbitrary byte boundaries", async () => {
    const chunks = [
      'event: session\ndata: {"session_id":"s1"}\n\nevent: stat',
      'us\ndata: {"stage":"routing","label":"질문을 분류하고 있어요"}\n\n',
      'event: done\ndata: {"latency_ms":50,"model_used":"claude-haiku-4-5","session_id":"s1"}\n\n',
    ];
    const received = [];
    for await (const event of readChatSSEStream(streamFrom(chunks))) {
      received.push(event);
    }
    expect(received).toEqual([
      { type: "session", session_id: "s1" },
      { type: "status", stage: "routing", label: "질문을 분류하고 있어요" },
      { type: "done", latency_ms: 50, model_used: "claude-haiku-4-5", session_id: "s1" },
    ]);
  });
});
