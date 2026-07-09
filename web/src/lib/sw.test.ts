import { readFileSync } from "node:fs";
import path from "node:path";
import { runInNewContext } from "node:vm";
import { afterEach, describe, expect, it, vi } from "vitest";

// public/sw.js is a plain classic script meant for direct browser
// registration (no bundler pass, no import), so it can't be imported like a
// normal module here. Instead we execute its source in a sandboxed vm
// context with fake `self`/`caches`/`fetch` globals and capture the
// listeners it registers via `self.addEventListener` — the same technique
// as testing a raw <script> tag's side effects.
// public/sw.js는 브라우저가 직접 등록하는 평범한 classic script라(번들러도
// import도 없음) 여기서 일반 모듈처럼 import할 수 없다. 대신 가짜
// `self`/`caches`/`fetch` 전역을 둔 vm 샌드박스에서 소스를 실행하고,
// `self.addEventListener`로 등록되는 리스너를 붙잡는다 — 원시 <script> 태그의
// 부수효과를 테스트하는 것과 같은 기법이다.
type Listener = (event: unknown) => unknown;

function loadServiceWorker() {
  const source = readFileSync(path.resolve(__dirname, "../../public/sw.js"), "utf-8");
  const listeners: Record<string, Listener> = {};
  const cacheStore = new Map<string, Response>();

  const fakeCache = {
    add: vi.fn(async (url: string) => {
      cacheStore.set(url, new Response(`cached:${url}`));
    }),
  };
  const fakeCaches = {
    open: vi.fn(async () => fakeCache),
    keys: vi.fn(async () => ["dajung-offline-v1", "stale-cache-v0"]),
    delete: vi.fn(async () => true),
    match: vi.fn(async (url: string) => cacheStore.get(url)),
  };
  const fakeSelf = {
    addEventListener: (type: string, cb: Listener) => {
      listeners[type] = cb;
    },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
  };
  const fakeFetch = vi.fn();

  runInNewContext(source, { self: fakeSelf, caches: fakeCaches, fetch: fakeFetch });

  return { listeners, cacheStore, fakeCache, fakeCaches, fakeSelf, fakeFetch };
}

describe("public/sw.js — install/activate lifecycle", () => {
  it("precaches exactly /offline and skips waiting on install", async () => {
    const { listeners, fakeCaches, fakeCache, fakeSelf } = loadServiceWorker();
    let waited: Promise<unknown> | undefined;
    const waitUntil = vi.fn((p: Promise<unknown>) => {
      waited = p;
    });
    listeners.install({ waitUntil });
    await waited;

    expect(fakeCaches.open).toHaveBeenCalledWith("dajung-offline-v1");
    expect(fakeCache.add).toHaveBeenCalledWith("/offline");
    expect(fakeCache.add).toHaveBeenCalledTimes(1);
    expect(fakeSelf.skipWaiting).toHaveBeenCalled();
  });

  it("drops stale caches and claims clients on activate", async () => {
    const { listeners, fakeCaches, fakeSelf } = loadServiceWorker();
    let waited: Promise<unknown> | undefined;
    const waitUntil = vi.fn((p: Promise<unknown>) => {
      waited = p;
    });
    listeners.activate({ waitUntil });
    await waited;

    expect(fakeCaches.delete).toHaveBeenCalledWith("stale-cache-v0");
    expect(fakeCaches.delete).not.toHaveBeenCalledWith("dajung-offline-v1");
    expect(fakeSelf.clients.claim).toHaveBeenCalled();
  });
});

describe("public/sw.js — fetch handler (network-only + offline fallback)", () => {
  afterEach(() => vi.clearAllMocks());

  it("ignores non-navigation requests entirely (network-only passthrough)", () => {
    const { listeners } = loadServiceWorker();
    const respondWith = vi.fn();
    listeners.fetch({ request: { mode: "cors" }, respondWith });

    expect(respondWith).not.toHaveBeenCalled();
  });

  it("passes a successful navigation fetch straight through", async () => {
    const { listeners, fakeFetch } = loadServiceWorker();
    const networkResponse = new Response("live page");
    fakeFetch.mockResolvedValue(networkResponse);

    let responded: Promise<Response> | undefined;
    const respondWith = vi.fn((p: Promise<Response>) => {
      responded = p;
    });
    listeners.fetch({ request: { mode: "navigate" }, respondWith });

    expect(await responded).toBe(networkResponse);
  });

  it("falls back to the cached /offline page when the network fetch rejects", async () => {
    const { listeners, fakeFetch, cacheStore } = loadServiceWorker();
    fakeFetch.mockRejectedValue(new TypeError("network unreachable"));
    cacheStore.set("/offline", new Response("offline page"));

    let responded: Promise<Response> | undefined;
    const respondWith = vi.fn((p: Promise<Response>) => {
      responded = p;
    });
    listeners.fetch({ request: { mode: "navigate" }, respondWith });

    const result = await responded;
    expect(await result?.text()).toBe("offline page");
  });
});
