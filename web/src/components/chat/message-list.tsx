"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import { Button } from "@/components/ui/button";
import { RagProgress } from "@/components/chat/rag-progress";
import { RoutePill } from "@/components/chat/route-pill";
import { CitationBadge } from "@/components/chat/citation-badge";
import { cn } from "@/lib/utils";
import type { ChatMessage, Citation } from "@/lib/chat-types";

// cite.py already strips out-of-range [n] markers from the answer, so every
// remaining `[n]` in content maps 1:1 to citations[n-1]. We rewrite them to
// `[n](#cite-n)` before handing the string to react-markdown so a normal
// markdown pass can render bold/lists/etc. around them, then swap the `a`
// element for a CitationBadge in `components` below — avoids a bespoke
// markdown parser just for inline citation markers.
// cite.py가 이미 범위 밖 [n] 마커를 answer에서 제거하므로, 남은 `[n]`은 전부
// citations[n-1]과 1:1 대응한다. react-markdown에 넘기기 전에 `[n](#cite-n)`
// 으로 바꿔서 굵게/목록 등이 주변에 있어도 일반 마크다운 패스로 처리되게 하고,
// 아래 `components`에서 `a`를 CitationBadge로 치환한다 — 인용 마커 하나 때문에
// 별도 마크다운 파서를 만들 필요가 없다.
function withCitationLinks(content: string): string {
  return content.replace(/\[(\d+)\]/g, "[$1](#cite-$1)");
}

function citationComponents(citations: Citation[]): Components {
  return {
    a({ href, children }) {
      const match = href?.match(/^#cite-(\d+)$/);
      const citation = match ? citations[Number(match[1]) - 1] : undefined;
      if (citation) return <CitationBadge citation={citation} />;
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
  };
}

function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-semantic-error bg-semantic-error-soft p-4 text-body-sm text-semantic-error">
      <p>{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="w-fit" onClick={onRetry}>
          다시 시도
        </Button>
      )}
    </div>
  );
}

export function MessageList({
  messages,
  ragLabel,
  onRetry,
}: {
  messages: ChatMessage[];
  ragLabel?: string | null;
  onRetry?: (messageId: string) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {messages.map((message) => {
        if (message.role === "user") {
          return (
            <div key={message.id} className="flex justify-end">
              <div className="max-w-[75%] rounded-lg bg-primary-soft px-4 py-2.5 text-body text-ink">
                {message.content}
              </div>
            </div>
          );
        }

        if (message.status === "error") {
          return (
            <div key={message.id} className="flex justify-start">
              <div className="max-w-[75%]">
                <ErrorCard
                  message={message.errorMessage ?? "응답 생성 중 오류가 발생했습니다."}
                  onRetry={onRetry ? () => onRetry(message.id) : undefined}
                />
              </div>
            </div>
          );
        }

        if (message.status === "streaming" && message.content === "") {
          return (
            <div key={message.id} className="flex justify-start">
              <RagProgress label={ragLabel ?? "질문을 분류하고 있어요"} />
            </div>
          );
        }

        return (
          <div key={message.id} className="flex justify-start">
            <div
              className={cn(
                "flex max-w-[75%] flex-col gap-2 rounded-lg border border-hairline bg-canvas p-4 text-body text-espresso",
              )}
            >
              {message.route && <RoutePill route={message.route} />}
              <div className="markdown-content">
                <ReactMarkdown components={citationComponents(message.citations ?? [])}>
                  {withCitationLinks(message.content)}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
