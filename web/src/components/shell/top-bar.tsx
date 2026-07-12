import Image from "next/image";
import Link from "next/link";
import { PageSwitcher } from "@/components/shell/page-switcher";
import { UserMenu } from "@/components/shell/user-menu";

export function TopBar({ userName }: { userName: string }) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-canvas px-5">
      <div className="flex items-center gap-4">
        <Link href="/chat" className="flex items-center gap-2 text-heading-4 text-ink">
          {/* unoptimized: sharp isn't in the standalone image (S8 Dockerfile) —
              Next's optimizer needs it in prod, and this fixed-size 192px
              source needs no transform at 20px anyway (webapp-spec S17). */}
          {/* unoptimized: standalone 이미지(S8 Dockerfile)에 sharp 없음 — Next
              옵티마이저는 프로덕션에서 sharp를 요구하는데, 이 고정 192px 원본은
              20px에서 어차피 변환이 불필요하다 (webapp-spec S17). */}
          <Image src="/icons/mascot-192.png" alt="다정 마스코트" width={20} height={20} unoptimized />
          Dajung AI
        </Link>
        <PageSwitcher />
      </div>
      <UserMenu name={userName} />
    </header>
  );
}
