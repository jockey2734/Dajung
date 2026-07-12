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
});
