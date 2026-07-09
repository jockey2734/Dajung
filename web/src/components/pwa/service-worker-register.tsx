"use client";

import { useEffect } from "react";

// Fire-and-forget — a failed/unsupported registration shouldn't block the
// app; the site works identically without a service worker, just without
// the offline fallback page (webapp-spec S7).
// 결과를 기다리지 않는다 — 등록 실패/미지원이 앱을 막아선 안 된다. 서비스
// 워커 없이도 사이트는 동일하게 동작하고, 다만 오프라인 폴백 페이지만
// 없어진다(webapp-spec S7).
export function ServiceWorkerRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  return null;
}
