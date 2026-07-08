import Link from "next/link";
import { PageSwitcher } from "@/components/shell/page-switcher";
import { UserMenu } from "@/components/shell/user-menu";

export function TopBar({ userName }: { userName: string }) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-canvas px-5">
      <div className="flex items-center gap-4">
        {/* Mascot placeholder — DESIGN.md Known Gaps: no vectorized logo yet. */}
        {/* 마스코트 임시 표기 — DESIGN.md Known Gaps: 벡터 로고 미완성. */}
        <Link href="/chat" className="flex items-center gap-2 text-heading-4 text-ink">
          <span aria-hidden>🍵</span>
          Dajung AI
        </Link>
        <PageSwitcher />
      </div>
      <UserMenu name={userName} />
    </header>
  );
}
