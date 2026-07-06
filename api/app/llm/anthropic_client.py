"""Anthropic API client wrapper (Dajung.md §8.12 — sync part pulled forward).

Anthropic API 클라이언트 래퍼 (Dajung.md §8.12 — sync 부분을 먼저 구현).
The ingest pipeline needs a simple synchronous complete(); the async/stream
surface for generate nodes lands with feat/cx-cli-rag.
ingest 파이프라인은 동기 complete()만 필요하다. generate 노드용
async/stream은 feat/cx-cli-rag에서 추가된다.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from api.app.core.config import settings


@lru_cache(maxsize=1)
def _client() -> Any:
    from anthropic import Anthropic

    return Anthropic(api_key=settings.anthropic_api_key or None)


def complete(
    model: str,
    system_blocks: list[dict[str, Any]],
    user_text: str,
    max_tokens: int,
) -> str:
    """Non-streaming completion; caller builds system blocks (incl. cache_control).

    논스트리밍 완성. system 블록(캐시 포함)은 호출자가 구성한다.
    """
    response = _client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_blocks if system_blocks else None,
        messages=[{"role": "user", "content": user_text}],
    )
    parts = [block.text for block in response.content if block.type == "text"]
    return "".join(parts)
