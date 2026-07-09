"use client";

import { HoverCard as HoverCardPrimitive } from "radix-ui";
import type { Citation } from "@/lib/chat-types";

// DESIGN.md citation-badge token: surface bg, mocha text, micro type, xs
// rounded, hairline border. Hover card shows source_file/locator/snippet
// (webapp-spec S4).
export function CitationBadge({ citation }: { citation: Citation }) {
  return (
    <HoverCardPrimitive.Root openDelay={150}>
      <HoverCardPrimitive.Trigger asChild>
        <button
          type="button"
          className="mx-0.5 inline-flex items-center rounded-xs border border-hairline bg-surface px-1.5 py-px align-super text-micro text-mocha"
        >
          [{citation.marker}]
        </button>
      </HoverCardPrimitive.Trigger>
      <HoverCardPrimitive.Portal>
        <HoverCardPrimitive.Content
          side="top"
          sideOffset={6}
          className="z-50 w-72 rounded-md border border-hairline bg-canvas p-3 text-body-sm text-ink shadow-md"
        >
          <p className="font-medium">{citation.source_file}</p>
          <p className="text-micro text-taupe">
            {citation.category} · {citation.locator}
            {citation.semester ? ` · ${citation.semester}` : ""}
          </p>
          <p className="mt-2 text-body-sm text-mocha">{citation.snippet}</p>
        </HoverCardPrimitive.Content>
      </HoverCardPrimitive.Portal>
    </HoverCardPrimitive.Root>
  );
}
