// Hand-rolled — no next-pwa/serwist/workbox (webapp-spec §11: no library
// beyond what a branch names; S7 names none). Plain classic script served
// from /sw.js and registered by service-worker-register.tsx.
// 직접 구현 — next-pwa/serwist/workbox 미사용(webapp-spec §11: 브랜치가
// 명시한 라이브러리 외 금지, S7은 아무것도 지목하지 않음). /sw.js로 서빙되는
// 평범한 classic script, service-worker-register.tsx가 등록한다.
const CACHE_NAME = "dajung-offline-v1";
const OFFLINE_URL = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.add(OFFLINE_URL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

// Network-only (webapp-spec S7) — the only thing ever served from cache is
// the /offline fallback, and only when a page navigation's network fetch
// fails outright. Every other request (API calls, assets, SSE) is left
// untouched: no event.respondWith(), so the browser's normal network fetch
// runs exactly as if no service worker were installed. This is also why no
// app data (sessions, messages, pantry) is ever cached here.
// network-only(webapp-spec S7) — 캐시에서 서빙하는 건 /offline 폴백
// 하나뿐이고, 그것도 페이지 네비게이션의 network fetch가 완전히 실패했을
// 때만이다. 그 외 모든 요청(API 호출·에셋·SSE)은 손대지 않는다:
// event.respondWith()를 호출하지 않아, SW가 없는 것처럼 브라우저의 평범한
// network fetch가 그대로 실행된다. 앱 데이터(세션·메시지·찻장)를 여기서
// 절대 캐싱하지 않는 이유도 이것이다.
self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;

  event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE_URL)));
});
