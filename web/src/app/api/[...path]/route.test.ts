import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const getTokenMock = vi.fn();
vi.mock("next-auth/jwt", () => ({ getToken: (...args: unknown[]) => getTokenMock(...args) }));

const { GET, POST } = await import("./route");

afterEach(() => {
  vi.unstubAllGlobals();
  getTokenMock.mockReset();
});

function fakeUpstream(body: BodyInit | null, init?: ResponseInit) {
  return new Response(body, init);
}

describe("BFF proxy /api/[...path]", () => {
  it("returns 401 unauthenticated without an Auth.js session, and never calls fetch", async () => {
    getTokenMock.mockResolvedValue(null);
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const req = new NextRequest("http://localhost:3000/api/pantry");
    const res = await GET(req, { params: Promise.resolve({ path: ["pantry"] }) });

    expect(res.status).toBe(401);
    const body = (await res.json()) as { error: { code: string } };
    expect(body.error.code).toBe("unauthenticated");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("attaches Authorization: Bearer <accessToken> and forwards path + query to API_BASE_URL", async () => {
    getTokenMock.mockResolvedValue({ accessToken: "jwt-abc" });
    const fetchSpy = vi
      .fn()
      .mockResolvedValue(fakeUpstream(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchSpy);

    const req = new NextRequest("http://localhost:3000/api/pantry?sort=name");
    const res = await GET(req, { params: Promise.resolve({ path: ["pantry"] }) });

    expect(res.status).toBe(200);
    const [target, init] = fetchSpy.mock.calls[0] as [URL, RequestInit];
    expect(target.toString()).toBe("http://api:8000/pantry?sort=name");
    const headers = init.headers as Headers;
    expect(headers.get("authorization")).toBe("Bearer jwt-abc");
  });

  it("streams the upstream body through for POST without buffering it into a new object", async () => {
    getTokenMock.mockResolvedValue({ accessToken: "jwt-abc" });
    const fetchSpy = vi
      .fn()
      .mockResolvedValue(
        fakeUpstream("event: done\ndata: {}\n\n", {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        }),
      );
    vi.stubGlobal("fetch", fetchSpy);

    const req = new NextRequest("http://localhost:3000/api/chat/stream", {
      method: "POST",
      body: JSON.stringify({ query: "hi" }),
    });
    const res = await POST(req, { params: Promise.resolve({ path: ["chat", "stream"] }) });

    expect(res.headers.get("content-type")).toBe("text/event-stream");
    expect(await res.text()).toBe("event: done\ndata: {}\n\n");

    const [, init] = fetchSpy.mock.calls[0] as [URL, RequestInit & { duplex?: string }];
    expect(init.method).toBe("POST");
    expect(init.duplex).toBe("half");
  });
});
