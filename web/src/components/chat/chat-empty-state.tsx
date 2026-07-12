import Image from "next/image";
import { cn } from "@/lib/utils";

// DESIGN.md `empty-state` (line 667) + `card-route-*` (line 601): chat's
// first-entry brand surface. Route keys/tints mirror route-pill.tsx exactly
// (api/app/graph/state.py Route enum values).
interface ExampleQuestion {
  route: "knowledge_query" | "handover_query" | "unclear";
  text: string;
}

const EXAMPLES: ExampleQuestion[] = [
  { route: "knowledge_query", text: "에스프레소 그라인더 청소는 얼마나 자주 해요?" },
  { route: "handover_query", text: "총무 인수인계 때 계좌·비품 뭘 넘겨야 해요?" },
  { route: "unclear", text: "다정은 어떤 동아리예요?" },
];

const ROUTE_CARD_STYLES: Record<ExampleQuestion["route"], { bg: string; text: string }> = {
  knowledge_query: { bg: "bg-route-knowledge", text: "text-route-knowledge-ink" },
  handover_query: { bg: "bg-route-handover", text: "text-route-handover-ink" },
  unclear: { bg: "bg-route-unclear", text: "text-route-unclear-ink" },
};

export function ChatEmptyState({
  show,
  onPickExample,
}: {
  show: boolean;
  onPickExample: (text: string) => void;
}) {
  if (!show) return null;

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 rounded-lg bg-cream px-6 py-10 text-center">
      {/* unoptimized — see top-bar.tsx: no sharp in the standalone image, and
          this fixed-size source needs no transform. */}
      {/* unoptimized — top-bar.tsx 참고: standalone 이미지에 sharp 없고, 고정
          크기 원본이라 변환이 불필요. */}
      <Image src="/icons/mascot-192.png" alt="다정 마스코트" width={48} height={48} unoptimized />
      <p className="text-body text-taupe">다정 AI에게 지식·인수인계·찻장 관련 질문을 해보세요.</p>
      <div className="grid w-full max-w-2xl gap-3 sm:grid-cols-3">
        {EXAMPLES.map((example) => {
          const style = ROUTE_CARD_STYLES[example.route];
          return (
            <button
              key={example.route}
              type="button"
              onClick={() => onPickExample(example.text)}
              className={cn(
                "rounded-lg p-4 text-left text-body-sm transition-opacity hover:opacity-90",
                style.bg,
                style.text,
              )}
            >
              {example.text}
            </button>
          );
        })}
      </div>
    </div>
  );
}
