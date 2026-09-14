"""LangGraph state and route definitions for MVP1 (Dajung.md §8.13).

MVP1용 LangGraph 상태·라우트 정의 (Dajung.md §8.13).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, TypedDict


class Route(StrEnum):
    """MVP1 router outcomes (ADR-012). budget/inventory arrive in MVP2/3.

    MVP1 라우터 결과 (ADR-012). budget/inventory는 MVP2/3에서 추가.
    """

    KNOWLEDGE_QUERY = "knowledge_query"
    HANDOVER_QUERY = "handover_query"
    UNCLEAR = "unclear"


class State(TypedDict, total=False):
    query: str
    user: dict[str, str]
    mode: Literal["rag", "web", "plain"]
    route: Route
    role_hint: str | None
    semester_hint: str | None
    topic_hint: str | None
    user_memory: str | None
    history: list[dict[str, str]]
    candidates: list[dict[str, Any]]
    reranked: list[dict[str, Any]]
    retries: int
    # Explicit next-node decision written by rerank_node (Dajung.md §8.15.3).
    # rerank_node가 기록하는 명시적 다음 노드 결정 (Dajung.md §8.15.3).
    route_after: str
    answer: str
    model_used: str
    citations: list[dict[str, Any]]
    offer: Literal["web_search"]
    # Finished exchange-rate prompt block from fx_context (webapp-spec S30) — never raw numbers.
    # fx_context가 완성한 환율 프롬프트 블록 (webapp-spec S30) — 숫자를 따로 담지 않는다.
    fx_block: str | None
