"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Coffee, FileText, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

const PAGES = [
  { href: "/chat", label: "채팅", icon: MessageSquare },
  { href: "/pantry", label: "찻장", icon: Coffee },
  { href: "/files", label: "자료", icon: FileText },
] as const;

export function PageSwitcher() {
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-1 rounded-full bg-surface p-1">
      {PAGES.map(({ href, label, icon: Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-body-sm-medium text-taupe transition-colors",
              active && "bg-canvas text-ink shadow-[0_1px_2px_0_rgba(15,15,15,0.06)]",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        );
      })}
    </div>
  );
}
