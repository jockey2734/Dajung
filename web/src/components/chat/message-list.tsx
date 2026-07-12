"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RagProgress } from "@/components/chat/rag-progress";
import { RoutePill } from "@/components/chat/route-pill";
import { CitationBadge } from "@/components/chat/citation-badge";
import { cn } from "@/lib/utils";
import { isPersistedMessageId, type ChatMessage, type Citation } from "@/lib/chat-types";

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

// webapp-spec S14: 👍/👎, same-button re-click clears the vote. Always
// faintly visible (not hover-only) so a returning user sees their prior vote
// without hovering. Only rendered for `status === "done"` messages with a
// real (non-turn-local) id — see isPersistedMessageId.
// webapp-spec S14: 👍/👎, 같은 버튼 재클릭은 투표 취소. hover 전용이 아니라
// 항상 흐리게 보여, 재방문 사용자가 hover 없이도 이전 투표를 볼 수 있게 한다.
// `status === "done"`이고 실제(턴 로컬 아닌) id를 가진 메시지에만 렌더된다
// — isPersistedMessageId 참고.
function FeedbackButtons({
  rating,
  onPick,
}: {
  rating: -1 | 1 | null | undefined;
  onPick: (rating: -1 | 1) => void;
}) {
  return (
    <div className="flex items-center gap-0.5">
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        aria-label="좋아요"
        aria-pressed={rating === 1}
        className={cn("opacity-60 hover:opacity-100", rating === 1 && "text-primary opacity-100")}
        onClick={() => onPick(1)}
      >
        <ThumbsUp className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        aria-label="싫어요"
        aria-pressed={rating === -1}
        className={cn("opacity-60 hover:opacity-100", rating === -1 && "text-primary opacity-100")}
        onClick={() => onPick(-1)}
      >
        <ThumbsDown className="size-3.5" />
      </Button>
    </div>
  );
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
  onFeedback,
}: {
  messages: ChatMessage[];
  ragLabel?: string | null;
  onRetry?: (messageId: string) => void;
  onFeedback?: (messageId: string, rating: -1 | 1) => void;
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
              {onFeedback && message.status === "done" && isPersistedMessageId(message.id) && (
                <FeedbackButtons
                  rating={message.myFeedback}
                  onPick={(rating) => onFeedback(message.id, rating)}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
