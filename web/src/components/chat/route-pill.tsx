import { cn } from "@/lib/utils";

// api/app/graph/state.py Route enum values -> DESIGN.md route-pill tint + label.
const ROUTE_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  knowledge_query: { label: "지식", bg: "bg-route-knowledge", text: "text-route-knowledge-ink" },
  handover_query: { label: "인수인계", bg: "bg-route-handover", text: "text-route-handover-ink" },
  unclear: { label: "되묻기", bg: "bg-route-unclear", text: "text-route-unclear-ink" },
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
