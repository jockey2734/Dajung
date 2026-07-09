"use client";

import { useEffect, useState } from "react";
import { CoffeeAlertOut } from "@/types/pantry";
import { X } from "lucide-react";

export function CoffeeAlertBanner({ alert }: { alert: CoffeeAlertOut | null }) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Spec: dismissal = sessionStorage
    if (typeof window !== "undefined") {
      const isDismissed = sessionStorage.getItem("dajung.pantry.alert.dismissed");
      if (isDismissed === "true") {
        setDismissed(true);
      }
    }
  }, []);

  const handleDismiss = () => {
    sessionStorage.setItem("dajung.pantry.alert.dismissed", "true");
    setDismissed(true);
  };

  if (!alert || !alert.alert || dismissed) {
    return null;
  }

  return (
    <div className="flex items-center justify-between bg-[#422A1E] text-[#FFF5DA] px-4 py-3 rounded-md mb-6 shadow-sm">
      <div className="flex items-center gap-2">
        <span>☕</span>
        <span className="font-medium text-sm">
          커피 원두 잔량 {alert.total_estimated_g}g — 보충이 필요합니다
        </span>
      </div>
      <button 
        onClick={handleDismiss}
        className="p-1 hover:bg-white/10 rounded-sm transition-colors"
        aria-label="닫기"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
