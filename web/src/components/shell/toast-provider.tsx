"use client";

import { useCallback, useEffect, useState } from "react";

// webapp-spec S20 needs two toast moments that outlive their page: transfer
// success navigates the demoted president to /chat, and an admin-API 403
// bounces the viewer out of /admin. Local component state dies with the
// navigation, so the message travels through sessionStorage: `flashToast()`
// writes it (and pings same-page listeners via a window event), and this
// provider — mounted once in the (app) layout — shows and clears it.
// webapp-spec S20의 토스트 두 곳은 페이지 이동을 넘어 살아야 한다: 이양 성공은
// 강등된 회장을 /chat으로 보내고, admin API 403은 /admin 밖으로 내보낸다.
// 컴포넌트 로컬 상태는 이동과 함께 죽으므로 메시지를 sessionStorage로 나른다 —
// `flashToast()`가 기록(같은 페이지 리스너에는 window 이벤트로 알림)하고,
// (app) 레이아웃에 한 번 마운트되는 이 프로바이더가 표시 후 지운다.

const STORAGE_KEY = "dajung.toast";
const EVENT_NAME = "dajung:toast";
const AUTO_DISMISS_MS = 5000;

export function flashToast(message: string): void {
  window.sessionStorage.setItem(STORAGE_KEY, message);
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function ToastProvider() {
  const [message, setMessage] = useState<string | null>(null);

  const consume = useCallback(() => {
    const stored = window.sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      setMessage(stored);
    }
  }, []);

  useEffect(() => {
    consume();
    window.addEventListener(EVENT_NAME, consume);
    return () => window.removeEventListener(EVENT_NAME, consume);
  }, [consume]);

  useEffect(() => {
    if (message === null) return;
    const id = setTimeout(() => setMessage(null), AUTO_DISMISS_MS);
    return () => clearTimeout(id);
  }, [message]);

  if (message === null) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-espresso px-4 py-2.5 text-body-sm text-cream shadow-lg"
    >
      {message}
    </div>
  );
}
