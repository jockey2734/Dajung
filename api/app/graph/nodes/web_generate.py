"""Explicit Anthropic web-search fallback generation."""

from __future__ import annotations

from typing import Any

from api.app.core.config import settings
from api.app.graph.history import prepend_history
from api.app.graph.state import State
from api.app.llm.anthropic_client import (
    complete_with_web_search,
    fallback_system_blocks,
)

WEB_DISCLAIMER = "(웹 검색 결과 — 동아리 내부 자료 아님)"


def web_generate_node(state: State) -> dict[str, Any]:
    """Generate from public web results after explicit user consent."""
    assert "query" in state
    user_text = prepend_history(f"질문: {state['query']}", state.get("history", []))
    answer, citations = complete_with_web_search(
        model=settings.model_sonnet,
        system_blocks=fallback_system_blocks("web", state.get("user_memory")),
        user_text=user_text,
        max_tokens=settings.max_tokens_generate,
        max_uses=settings.web_search_max_uses,
    )
    body = answer.strip()
    return {
        "answer": f"{WEB_DISCLAIMER}\n{body}" if body else WEB_DISCLAIMER,
        "model_used": settings.model_sonnet,
        "citations": citations,
    }
