"""Deterministic consent prompt after exhausted low-confidence RAG."""

from __future__ import annotations

from typing import Any

from api.app.graph.state import State

OFFER_WEB_MESSAGE = "문서 검색에 실패했습니다. 웹 검색을 시도해보시겠습니까?"


def offer_web_node(state: State) -> dict[str, Any]:
    """End the RAG turn with a web-search offer."""
    assert "query" in state
    return {
        "answer": OFFER_WEB_MESSAGE,
        "model_used": "none",
        "offer": "web_search",
        "citations": [],
    }
