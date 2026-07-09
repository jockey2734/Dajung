"use client";

import { useEffect, useState } from "react";
import { MoreHorizontal, PanelLeft, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/relative-time";
import type { SessionSummary } from "@/lib/chat-types";

// webapp-spec S4: exact key so a saved preference survives across sessions.
const SIDEBAR_STORAGE_KEY = "dajung.sidebar";

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNewChat,
  onDelete,
}: {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}) {
  // Defaults to expanded on the server render; the effect below reconciles
  // with localStorage right after mount (avoids an SSR/client markup
  // mismatch since localStorage doesn't exist on the server).
  // 서버 렌더는 펼침 기본값으로 시작하고, 마운트 직후 effect가 localStorage와
  // 맞춘다(localStorage가 서버엔 없어 SSR/클라이언트 마크업 불일치 방지).
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "collapsed");
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? "collapsed" : "expanded");
      return next;
    });
  }

  if (collapsed) {
    return (
      <div className="flex w-12 flex-col items-center gap-2 border-r border-hairline bg-surface py-3">
        <Button variant="ghost" size="icon" aria-label="세션 사이드바 펼치기" onClick={toggleCollapsed}>
          <PanelLeft className="size-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex w-[clamp(280px,25%,400px)] flex-col border-r border-hairline bg-surface">
      <div className="flex items-center gap-2 p-3">
        <Button className="flex-1 justify-start gap-2" onClick={onNewChat}>
          <Plus className="size-4" />새 채팅
        </Button>
        <Button variant="ghost" size="icon" aria-label="세션 사이드바 접기" onClick={toggleCollapsed}>
          <PanelLeft className="size-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={cn(
              "group flex items-center gap-1 rounded-md px-2.5 py-2 text-body-sm text-ink hover:bg-hairline-soft",
              session.id === activeSessionId && "bg-primary-soft",
            )}
          >
            <button
              type="button"
              onClick={() => onSelect(session.id)}
              className="flex min-w-0 flex-1 flex-col items-start text-left"
            >
              <span className="w-full truncate">{session.title}</span>
              {session.lastMessageAt && (
                <span className="text-micro text-taupe">{formatRelativeTime(session.lastMessageAt)}</span>
              )}
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`${session.title} 메뉴`}
                  className="opacity-0 group-hover:opacity-100"
                >
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem variant="destructive" onSelect={() => onDelete(session.id)}>
                  <Trash2 />
                  삭제
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ))}
      </div>
    </div>
  );
}
