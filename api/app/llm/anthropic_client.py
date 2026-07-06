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


# Common answer rules for every generate path (Dajung.md §8.12).
# 모든 생성 경로의 공통 답변 규칙 (Dajung.md §8.12).
ANSWER_RULES = """답변 규칙:
1. 아래 제공된 자료에 근거해서만 답한다. 자료에 없는 내용은 추측하지 않는다.
2. 자료가 질문에 답하기에 부족하면 "관련 자료를 찾지 못했습니다"라고 밝히고,
   어떤 자료를 검색했는지 한 줄로 알려준다.
3. 자료를 인용한 모든 문장 끝에 [번호] 마커를 붙인다. 번호는 제공된 자료 번호다.
4. 자료에 없는 일반 상식을 보조적으로 쓸 때는 "(일반 지식)"이라고 표시한다."""

_DEFAULT_TONE = (
    "너는 다정(성균관대 커피·차 동아리) 운영진 업무 보조 AI다. 정중하고 간결한 한국어로 답한다."
)


def load_tone_prompt() -> str:
    """Load the tone prompt from prompts/persona/tone.md, else the default.

    prompts/persona/tone.md가 있으면 읽고, 없으면 기본 톤을 쓴다.
    """
    path = settings.prompts_dir / "persona" / "tone.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return _DEFAULT_TONE


def answer_system_blocks() -> list[dict[str, Any]]:
    """System blocks for generate calls — tone + rules, both cached.

    생성 호출용 system 블록 — 톤 + 규칙, 둘 다 캐시.
    """
    return [
        {"type": "text", "text": load_tone_prompt(), "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": ANSWER_RULES, "cache_control": {"type": "ephemeral"}},
    ]


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
