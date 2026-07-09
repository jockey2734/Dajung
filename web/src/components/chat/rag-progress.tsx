"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

// webapp-spec S4: dots cycle 1->2->3, 400ms interval, sand->espresso.
// webapp-spec S4: 점 1→2→3 순환, 400ms 간격, sand→espresso.
const DOT_INTERVAL_MS = 400;

// Mascot is the same temp emoji used in top-bar.tsx — DESIGN.md Known Gaps,
// no vectorized asset yet (S3 already established this as an allowed deviation).
// 마스코트는 top-bar.tsx와 동일한 임시 이모지 — DESIGN.md Known Gaps, 벡터
// 자산 미완성(S3에서 이미 허용된 이탈로 확정).
export function RagProgress({ label }: { label: string }) {
  const [activeDots, setActiveDots] = useState(1);

  useEffect(() => {
    const id = setInterval(() => {
      setActiveDots((n) => (n % 3) + 1);
    }, DOT_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-3 py-2" role="status" aria-live="polite">
      <span aria-hidden className="text-[32px] leading-none">
        🍵
      </span>
      <div className="flex flex-col gap-1.5">
        <p className="text-body-sm text-taupe">{label}</p>
        <div className="flex gap-1">
          {[1, 2, 3].map((dot) => (
            <span
              key={dot}
              className={cn(
                "size-1.5 rounded-full transition-colors duration-200",
                dot <= activeDots ? "bg-espresso" : "bg-sand",
              )}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
