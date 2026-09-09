import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useChatStream } from "./use-chat-stream";

function streamResponse(payload: string): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(payload));
      controller.close();
    },
  });
  return new Response(body, {
    headers: { "content-type": "text/event-stream" },
  });
}

describe("useChatStream", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses server-provided done.remaining instead of local countdown", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ sessions: [] }),
      })
      .mockResolvedValueOnce(
        streamResponse(
          'event: done\ndata: {"latency_ms":40,"model_used":"claude-haiku-4-5","session_id":"s1","remaining":12}\n\n',
        ),
      )
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ sessions: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "s1", title: "t", messages: [] }),
      });

    const { result } = renderHook(() => useChatStream());

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));
    expect(result.current.remaining).toBe(20);

    await act(async () => {
      result.current.sendMessage("질문");
    });

    await waitFor(() => expect(result.current.remaining).toBe(12));
  });

  // After `done`, the turn-local assistant id gets swapped for the DB id via
  // a session-detail refetch — feedback needs that real id.
  // `done` 이후 턴 로컬 assistant id가 세션 상세 재조회로 DB id로 교체된다 —
  // 피드백은 이 실제 id가 필요하다.
  it("swaps turn-local message ids for real ones after done", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce(
        streamResponse(
          'event: session\ndata: {"session_id":"s1"}\n\n' +
            'event: done\ndata: {"latency_ms":40,"model_used":"claude-haiku-4-5","session_id":"s1","remaining":12}\n\n',
        ),
      )
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "s1",
          title: "t",
          messages: [
            {
              id: "real-assistant-id",
              role: "assistant",
              content: "답변",
              metadata: {},
              created_at: "2026-01-01T00:00:00Z",
              my_feedback: null,
            },
          ],
        }),
      });

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));

    await act(async () => {
      result.current.sendMessage("질문");
    });

    await waitFor(() =>
      expect(result.current.messages.some((m) => m.id === "real-assistant-id")).toBe(true),
    );
  });

  it("restores my_feedback when a session is loaded", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "s1",
          title: "t",
          messages: [
            {
              id: "m1",
              role: "assistant",
              content: "답변",
              metadata: {},
              created_at: "2026-01-01T00:00:00Z",
              my_feedback: 1,
            },
          ],
        }),
      });

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));

    await act(async () => {
      await result.current.selectSession("s1");
    });

    expect(result.current.messages[0].myFeedback).toBe(1);
  });

  // webapp-spec S29: loaded rows carry the DB created_at; a live turn is
  // stamped with the client clock until the post-done refresh replaces it.
  // webapp-spec S29: 로드된 행은 DB created_at을 가지고, 라이브 턴은 done 후
  // 새로고침이 교체하기 전까지 클라이언트 시각이 찍힌다.
  it("maps created_at onto createdAt for loaded rows and stamps live turns with the client clock", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "s1",
          title: "t",
          messages: [
            {
              id: "m1",
              role: "user",
              content: "질문",
              metadata: {},
              created_at: "2026-01-01T00:00:00Z",
              my_feedback: null,
            },
          ],
        }),
      })
      // Non-SSE failure keeps the live turn's client-side rows in place.
      // SSE가 아닌 실패는 라이브 턴의 클라이언트 행을 그대로 남긴다.
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { message: "실패" } }), {
          status: 500,
          headers: { "content-type": "application/json" },
        }),
      );

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));

    await act(async () => {
      await result.current.selectSession("s1");
    });
    expect(result.current.messages[0].createdAt).toBe("2026-01-01T00:00:00Z");

    const before = Date.now();
    await act(async () => {
      result.current.sendMessage("새 질문");
    });
    await waitFor(() => expect(result.current.messages).toHaveLength(3));

    const [, liveUser, liveAssistant] = result.current.messages;
    expect(liveUser.createdAt).toBeDefined();
    expect(liveAssistant.createdAt).toBe(liveUser.createdAt);
    const stamped = new Date(liveUser.createdAt as string).getTime();
    expect(stamped).toBeGreaterThanOrEqual(before);
    expect(stamped).toBeLessThanOrEqual(Date.now());
  });

  it("setFeedback: click sends PUT, re-click sends DELETE, other button replaces via PUT", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "s1",
          title: "t",
          messages: [
            {
              id: "m1",
              role: "assistant",
              content: "답변",
              metadata: {},
              created_at: "2026-01-01T00:00:00Z",
              my_feedback: null,
            },
          ],
        }),
      });

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));
    await act(async () => {
      await result.current.selectSession("s1");
    });

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await act(async () => {
      await result.current.setFeedback("m1", 1);
    });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/messages/m1/feedback", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating: 1 }),
    });
    expect(result.current.messages[0].myFeedback).toBe(1);

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await act(async () => {
      await result.current.setFeedback("m1", 1);
    });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/messages/m1/feedback", { method: "DELETE" });
    expect(result.current.messages[0].myFeedback).toBe(null);

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await act(async () => {
      await result.current.setFeedback("m1", -1);
    });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/messages/m1/feedback", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating: -1 }),
    });
    expect(result.current.messages[0].myFeedback).toBe(-1);
  });

  it("setFeedback: rolls back the optimistic update on failure", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "s1",
          title: "t",
          messages: [
            {
              id: "m1",
              role: "assistant",
              content: "답변",
              metadata: {},
              created_at: "2026-01-01T00:00:00Z",
              my_feedback: null,
            },
          ],
        }),
      });

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));
    await act(async () => {
      await result.current.selectSession("s1");
    });

    fetchMock.mockResolvedValueOnce({ ok: false });
    await act(async () => {
      await result.current.setFeedback("m1", 1);
    });

    expect(result.current.messages[0].myFeedback).toBe(null);
  });

  // webapp-spec S27: the offer arrives on done and must survive the internal
  // post-done id swap (refreshMessages) — but only for the live turn, never
  // restored from session metadata.
  // webapp-spec S27: 제안은 done으로 도착하고 done 직후 내부 id 교체
  // (refreshMessages)를 견뎌야 한다 — 단 라이브 턴에서만, 세션 metadata
  // 복원은 없다.
  function offerTurnMocks(fetchMock: ReturnType<typeof vi.fn>) {
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce(
        streamResponse(
          'event: session\ndata: {"session_id":"s1"}\n\n' +
            'event: done\ndata: {"latency_ms":40,"model_used":"","session_id":"s1","remaining":12,"offer":"web_search"}\n\n',
        ),
      )
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "s1",
          title: "t",
          messages: [
            {
              id: "real-u1",
              role: "user",
              content: "원래 질문",
              metadata: {},
              created_at: "2026-01-01T00:00:00Z",
              my_feedback: null,
            },
            {
              id: "real-a1",
              role: "assistant",
              content: "문서 검색에 실패했습니다. 웹 검색을 시도해보시겠습니까?",
              metadata: { route: "knowledge_query", offer: "web_search" },
              created_at: "2026-01-01T00:00:01Z",
              my_feedback: null,
            },
          ],
        }),
      });
  }

  it("keeps done.offer and the original question on the turn across the id swap", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    offerTurnMocks(fetchMock);

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));

    await act(async () => {
      result.current.sendMessage("원래 질문");
    });

    await waitFor(() => {
      const offered = result.current.messages.find((m) => m.id === "real-a1");
      expect(offered?.offer).toBe("web_search");
      expect(offered?.retryQuery).toBe("원래 질문");
    });
    // The rag turn's request body must not carry a mode field.
    // rag 턴의 요청 바디에는 mode 필드가 없어야 한다.
    const [, ragInit] = fetchMock.mock.calls.find(([url]) => url === "/api/chat/stream") as [
      string,
      { body: string },
    ];
    expect(JSON.parse(ragInit.body)).not.toHaveProperty("mode");
  });

  it("acceptOffer resends the original question as a new turn with the picked mode and consumes the offer", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    offerTurnMocks(fetchMock);

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));

    await act(async () => {
      result.current.sendMessage("원래 질문");
    });
    await waitFor(() =>
      expect(result.current.messages.find((m) => m.id === "real-a1")?.offer).toBe("web_search"),
    );

    // The follow-up turn errors out on purpose: the error path skips the
    // refetch, so the consumed flag stays observable without racing it.
    // 후속 턴은 일부러 에러로 끝낸다: 에러 경로는 재조회를 건너뛰므로 소비
    // 플래그를 경합 없이 관찰할 수 있다.
    fetchMock.mockResolvedValueOnce(
      streamResponse('event: error\ndata: {"error":{"code":"llm_down","message":"오류"}}\n\n'),
    );

    await act(async () => {
      result.current.acceptOffer("real-a1", "web");
    });

    const streamCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/chat/stream");
    expect(streamCalls).toHaveLength(2);
    const body = JSON.parse((streamCalls[1][1] as { body: string }).body) as {
      query: string;
      mode: string;
    };
    expect(body.query).toBe("원래 질문");
    expect(body.mode).toBe("web");
    expect(result.current.messages.find((m) => m.id === "real-a1")?.offerConsumed).toBe(true);

    // Second click is a no-op — the offer is already consumed.
    // 두 번째 클릭은 no-op — 제안이 이미 소비됐다.
    await act(async () => {
      result.current.acceptOffer("real-a1", "plain");
    });
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/chat/stream")).toHaveLength(2);
  });

  it("does not restore offer buttons when a session is re-opened (live-stream-only)", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ sessions: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "s1",
          title: "t",
          messages: [
            {
              id: "real-a1",
              role: "assistant",
              content: "문서 검색에 실패했습니다. 웹 검색을 시도해보시겠습니까?",
              metadata: { route: "knowledge_query", offer: "web_search" },
              created_at: "2026-01-01T00:00:01Z",
              my_feedback: null,
            },
          ],
        }),
      });

    const { result } = renderHook(() => useChatStream());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));

    await act(async () => {
      await result.current.selectSession("s1");
    });

    expect(result.current.messages[0].offer).toBeUndefined();
  });
});
