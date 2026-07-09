import Link from "next/link";

// Server Component, no client JS required to render or to "retry" — Link
// always renders a real <a href>, so the browser can navigate on it even if
// this page's JS chunks weren't in the SW's single precached response
// (webapp-spec S7: 유일한 캐시 = /offline 문서 자체 하나) and hydration
// never ran.
// Mascot reuses the same temp emoji as top-bar.tsx/rag-progress.tsx rather
// than the manifest icon PNGs, so nothing extra needs to be cached for this
// page to render correctly with zero network (DESIGN.md Known Gaps).
// 서버 컴포넌트, 렌더링에도 "재시도"에도 클라이언트 JS 불필요 — Link는 항상
// 진짜 <a href>를 렌더하므로, 이 페이지 JS 청크가 SW의 단일 사전 캐시
// 응답(webapp-spec S7: 유일한 캐시 = /offline 문서 자체 하나)에 없어 hydration이
// 안 됐어도 브라우저가 그냥 이동한다.
// 마스코트는 manifest 아이콘 PNG 대신 top-bar.tsx/rag-progress.tsx와 같은
// 임시 이모지를 재사용 — 이 페이지가 네트워크 0인 상태에서도 제대로 렌더되도록
// 추가로 캐싱할 게 없게 한다(DESIGN.md Known Gaps).
export default function OfflinePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-cream px-6 text-center">
      <span aria-hidden className="text-[64px] leading-none">
        🍵
      </span>
      <p className="text-heading-3 text-ink">인터넷을 연결하시오</p>
      <Link
        href="/"
        className="inline-flex h-8 items-center justify-center rounded-lg bg-primary px-4 text-button font-medium text-on-primary"
      >
        다시 시도
      </Link>
    </div>
  );
}
