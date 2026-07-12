"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

// webapp-spec S4: dots cycle 1->2->3, 400ms interval, sand->espresso.
// webapp-spec S4: 점 1→2→3 순환, 400ms 간격, sand→espresso.
const DOT_INTERVAL_MS = 400;

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
      {/* unoptimized — see top-bar.tsx: no sharp in the standalone image, and
          this fixed-size source needs no transform. */}
      {/* unoptimized — top-bar.tsx 참고: standalone 이미지에 sharp 없고, 고정
          크기 원본이라 변환이 불필요. */}
      <Image src="/icons/mascot-192.png" alt="다정 마스코트" width={32} height={32} unoptimized />
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
