"""Generate node — knowledge answers with citations (Dajung.md §8.15.4).

생성 노드 — 인용 포함 지식 답변 (Dajung.md §8.15.4).
"""

from __future__ import annotations

from typing import Any

from api.app.core.config import settings
from api.app.graph.state import State
from api.app.llm.anthropic_client import answer_system_blocks, complete
from api.app.rag.answer import build_context, pick_model

_NO_SOURCE_ANSWER = (
    "관련 자료를 찾지 못했습니다. 인덱싱된 자료가 있는지 `dajung stats`로 확인하세요."
)


def generate_node(state: State) -> dict[str, Any]:
    """Answer from reranked context only; honest empty-result message.

    리랭크된 자료만으로 답한다. 자료 없으면 정직하게 없다고 답한다.
    """
    assert "reranked" in state and "query" in state
    reranked = state["reranked"]
    if not reranked:
        return {"answer": _NO_SOURCE_ANSWER, "model_used": "none"}

    model = pick_model("knowledge", state["query"], len(reranked))
    answer = complete(
        model=model,
        system_blocks=answer_system_blocks(),
        user_text=f"질문: {state['query']}\n\n자료:\n{build_context(reranked)}",
        max_tokens=settings.max_tokens_generate,
    )
    return {"answer": answer, "model_used": model}
