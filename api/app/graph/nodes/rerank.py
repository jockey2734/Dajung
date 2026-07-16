"""Rerank node + explicit next-node decision (Dajung.md §8.15.3).

리랭크 노드 + 명시적 다음 노드 결정 (Dajung.md §8.15.3).
The node writes `route_after` so the conditional edge stays a pure lookup —
no re-derivation, no retry-count ambiguity.
노드가 `route_after`를 기록해 조건부 엣지는 순수 조회만 한다 —
재계산도, retry 카운트 모호함도 없다.
"""

from __future__ import annotations

from typing import Any

from api.app.core.config import settings
from api.app.graph.state import Route, State
from api.app.rag.reranker import rerank

_RETRIEVE_FOR = {
    Route.HANDOVER_QUERY: "retrieve_handover",
    Route.KNOWLEDGE_QUERY: "retrieve_knowledge",
}
_GENERATE_FOR = {
    Route.HANDOVER_QUERY: "generate_handover",
    Route.KNOWLEDGE_QUERY: "generate",
}


def rerank_node(state: State) -> dict[str, Any]:
    """Rerank candidates and decide: one retry with original filters, or generate.

    후보를 리랭크하고 결정한다: 원 필터 유지 재검색 1회 또는 생성.
    """
    assert "candidates" in state and "query" in state and "route" in state
    reranked = rerank(state["query"], state["candidates"])
    retries = state.get("retries", 0)
    route = state["route"]

    top = float(reranked[0]["rerank_score"]) if reranked else 0.0
    if top < settings.rerank_threshold:
        if retries < settings.max_retries:
            # Retry via the ORIGINAL route's retrieve node — keeps its filters.
            # 원래 route의 retrieve로 재시도 — 필터가 유지된다.
            return {
                "reranked": reranked,
                "retries": retries + 1,
                "route_after": _RETRIEVE_FOR.get(route, "retrieve_knowledge"),
            }
        if route in _GENERATE_FOR:
            return {"reranked": reranked, "route_after": "offer_web"}
    return {
        "reranked": reranked,
        "route_after": _GENERATE_FOR.get(route, "generate"),
    }


def route_after_rerank(state: State) -> str:
    """Conditional-edge selector — pure lookup of the node's decision.

    조건부 엣지 선택자 — 노드 결정의 순수 조회.
    """
    return state["route_after"]
