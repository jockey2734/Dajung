"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import { Globe, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RagProgress } from "@/components/chat/rag-progress";
import { RoutePill } from "@/components/chat/route-pill";
import { CitationBadge } from "@/components/chat/citation-badge";
import { cn } from "@/lib/utils";
import {
  isPersistedMessageId,
  type ChatMessage,
  type Citation,
  type FallbackMode,
  type WebCitation,
} from "@/lib/chat-types";

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
      // Web citations carry no marker and never pair with an inline [n] —
      // only doc-shaped items (kind absent = pre-S26 doc row) become badges.
      // 웹 인용은 marker가 없고 인라인 [n]과 짝지어지지 않는다 — doc 형태
      // 항목(kind 부재 = S26 이전 doc 행)만 배지가 된다.
      if (citation && citation.kind !== "web") return <CitationBadge citation={citation} />;
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
  };
}

// webapp-spec S27: kind:"web" sources render as an external-link list,
// visually distinct from doc badges (globe icon, soft background). The
// disclaimer line comes inside the answer body from the backend — nothing
// duplicated here.
// webapp-spec S27: kind:"web" 출처는 외부 링크 리스트로, doc 배지와 시각
// 구분(지구본 아이콘·연한 배경). 디스클레이머 문구는 백엔드가 답변 본문에
// 넣어 보내므로 여기서 중복 표기하지 않는다.
function WebSourceList({ citations }: { citations: WebCitation[] }) {
  return (
    <ul className="flex flex-col gap-1 rounded-md border border-hairline bg-surface p-2.5">
      {citations.map((citation) => (
        <li key={citation.url}>
          <a
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-body-sm text-mocha underline-offset-2 hover:underline"
          >
            <Globe aria-hidden className="size-3.5 shrink-0" />
            {citation.title}
          </a>
        </li>
      ))}
    </ul>
  );
}

// webapp-spec S27: rendered under the offer message from the live stream.
// One click disables both buttons; `locked` additionally disables them while
// any other stream is in flight so a stale offer can't start a second
// concurrent turn.
// webapp-spec S27: 라이브 스트림의 제안 메시지 아래에 렌더된다. 한 번
// 클릭하면 두 버튼 모두 비활성. `locked`는 다른 스트림 진행 중에도
// 비활성화해, 지난 제안이 동시 턴을 하나 더 만들지 못하게 한다.
function OfferButtons({
  consumed,
  locked,
  onPick,
}: {
  consumed: boolean;
  locked: boolean;
  onPick: (mode: FallbackMode) => void;
}) {
  const disabled = consumed || locked;
  return (
    <div className="flex items-center gap-2">
      <Button type="button" variant="secondary" size="sm" disabled={disabled} onClick={() => onPick("web")}>
        웹에서 검색
      </Button>
      <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => onPick("plain")}>
        그냥 답변 받기
      </Button>
    </div>
  );
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
  onAcceptOffer,
  offerLocked = false,
}: {
  messages: ChatMessage[];
  ragLabel?: string | null;
  onRetry?: (messageId: string) => void;
  onFeedback?: (messageId: string, rating: -1 | 1) => void;
  onAcceptOffer?: (messageId: string, mode: FallbackMode) => void;
  offerLocked?: boolean;
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

        const webCitations = (message.citations ?? []).filter(
          (citation): citation is WebCitation => citation.kind === "web",
        );

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
              {webCitations.length > 0 && <WebSourceList citations={webCitations} />}
              {onAcceptOffer && message.status === "done" && message.offer === "web_search" && (
                <OfferButtons
                  consumed={message.offerConsumed === true}
                  locked={offerLocked}
                  onPick={(mode) => onAcceptOffer(message.id, mode)}
                />
              )}
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
