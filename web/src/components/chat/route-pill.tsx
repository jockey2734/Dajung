import { cn } from "@/lib/utils";

// api/app/graph/state.py Route enum values -> DESIGN.md route-pill tint + label.
// "web"/"plain" are the S26 fallback modes stored as the assistant meta route
// (webapp-spec S27 stream-contract note) — without entries here they would
// fall back to the misleading "되묻기" pill. No dedicated tokens in DESIGN.md
// yet, so they reuse the neutral unclear tint.
// "web"/"plain"은 assistant meta route로 저장되는 S26 폴백 모드다
// (webapp-spec S27 스트림 계약 주의) — 여기 항목이 없으면 오해를 부르는
// "되묻기" 필로 떨어진다. DESIGN.md에 전용 토큰이 아직 없어 중립 unclear
// 색을 재사용한다.
const ROUTE_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  knowledge_query: { label: "지식", bg: "bg-route-knowledge", text: "text-route-knowledge-ink" },
  handover_query: { label: "인수인계", bg: "bg-route-handover", text: "text-route-handover-ink" },
  unclear: { label: "되묻기", bg: "bg-route-unclear", text: "text-route-unclear-ink" },
  web: { label: "웹 검색", bg: "bg-route-unclear", text: "text-route-unclear-ink" },
  plain: { label: "일반 답변", bg: "bg-route-unclear", text: "text-route-unclear-ink" },
};

export function RoutePill({ route }: { route: string }) {
  const style = ROUTE_STYLES[route] ?? ROUTE_STYLES.unclear;
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center rounded-full px-2.5 py-1 text-micro-uppercase font-medium uppercase tracking-wide",
        style.bg,
        style.text,
      )}
    >
      {style.label}
    </span>
  );
}
