"""Explicit ungrounded general-knowledge fallback generation.

명시적으로 선택한 무근거 일반 지식 폴백 생성.
"""

from __future__ import annotations

from typing import Any

from api.app.core.config import settings
from api.app.graph.history import prepend_history
from api.app.graph.state import State
from api.app.llm.anthropic_client import (
    REFUSAL_ANSWER,
    ModelRefusalError,
    complete,
    fallback_system_blocks,
)

PLAIN_DISCLAIMER = "(동아리 자료·웹 근거 없음 — 일반 지식 답변)"


def plain_generate_node(state: State) -> dict[str, Any]:
    """Generate without document or web evidence after explicit choice.

    사용자의 명시적 선택 뒤 문서나 웹 근거 없이 답한다.
    """
    assert "query" in state
    user_text = prepend_history(f"질문: {state['query']}", state.get("history", []))
    try:
        answer = complete(
            model=settings.model_sonnet,
            system_blocks=fallback_system_blocks("plain", state.get("user_memory")),
            user_text=user_text,
            max_tokens=settings.max_tokens_generate,
            effort=settings.sonnet_effort_other,
        )
    except ModelRefusalError:
        return {"answer": REFUSAL_ANSWER, "model_used": settings.model_sonnet, "citations": []}
    body = answer.strip()
    return {
        "answer": f"{PLAIN_DISCLAIMER}\n{body}" if body else PLAIN_DISCLAIMER,
        "model_used": settings.model_sonnet,
        "citations": [],
    }
