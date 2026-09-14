"""Handover generate node — structured 4-section answer (Dajung.md §8.15.5).

인수인계 생성 노드 — 4섹션 구조화 답변 (Dajung.md §8.15.5).
"""

from __future__ import annotations

from typing import Any

from api.app.core.config import settings
from api.app.graph.history import prepend_history
from api.app.graph.nodes.fx_context import prepend_fx_block
from api.app.graph.state import State
from api.app.llm.anthropic_client import answer_system_blocks, complete
from api.app.rag.answer import build_context

_FORMAT = (
    "다음 4개 섹션으로 답하라: ## 해야 할 일 / ## 주의할 일 / "
    "## 확인할 문서 / ## 사람에게 확인할 부분\n"
    "각 항목은 불릿으로, 자료 근거 있는 항목엔 [번호] 마커."
)

_NO_SOURCE_ANSWER = (
    "인수인계 관련 자료를 찾지 못했습니다. 인덱싱된 자료가 있는지 `dajung stats`로 확인하세요."
)


def generate_handover(state: State) -> dict[str, Any]:
    """Sonnet-fixed structured synthesis across handover documents.

    인수인계 문서군을 Sonnet 고정으로 구조화 종합한다.
    """
    assert "reranked" in state and "query" in state
    reranked = state["reranked"]
    if not reranked:
        return {"answer": _NO_SOURCE_ANSWER, "model_used": "none"}

    role_hint = state.get("role_hint")
    role_line = f"질문자 직책: {role_hint}\n" if role_hint else ""
    material = prepend_fx_block(f"자료:\n{build_context(reranked)}", state.get("fx_block"))
    user_text = f"{_FORMAT}\n\n{role_line}질문: {state['query']}\n\n{material}"
    answer = complete(
        model=settings.model_sonnet,
        system_blocks=answer_system_blocks(state.get("user_memory")),
        user_text=prepend_history(user_text, state.get("history", [])),
        max_tokens=settings.max_tokens_generate,
    )
    return {"answer": answer, "model_used": settings.model_sonnet}
