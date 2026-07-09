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
      });

    const { result } = renderHook(() => useChatStream());

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions"));
    expect(result.current.remaining).toBe(20);

    await act(async () => {
      result.current.sendMessage("질문");
    });

    await waitFor(() => expect(result.current.remaining).toBe(12));
  });
});
