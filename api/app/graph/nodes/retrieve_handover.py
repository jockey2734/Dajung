"""Handover retrieval node — multi doc_type + hint filters (§8.15.2).

인수인계 검색 노드 — 다중 doc_type + 힌트 필터 (§8.15.2).
"""

from __future__ import annotations

from typing import Any

from qdrant_client.models import Condition, FieldCondition, Filter, MatchAny, MatchValue

from api.app.core.config import settings
from api.app.graph.state import State
from api.app.rag.qdrant_store import build_permission_filter, hybrid_search

# Handover questions synthesize across these document kinds (system-design §3.3).
# 인수인계 질문은 이 문서 종류들을 종합한다 (system-design §3.3).
HANDOVER_DOC_TYPES = ["handover", "minutes", "budget", "checklist", "operation_rule", "admin_doc"]


def build_handover_filter(user: dict[str, str], semester_hint: str | None) -> Filter:
    """Permission AND doc_type must; semester as a soft should boost.

    권한 AND doc_type은 must, semester는 가점(should)으로만.
    """
    must: list[Condition | Filter] = [
        FieldCondition(key="doc_type", match=MatchAny(any=HANDOVER_DOC_TYPES))
    ]
    perm = build_permission_filter(user)
    if perm is not None:
        must.append(perm)
    should: list[Condition | Filter] = []
    if semester_hint:
        # Soft boost only — old-semester docs stay useful for handover.
        # 가점만 — 과거 학기 자료도 인수인계엔 유용하다.
        should.append(FieldCondition(key="semester", match=MatchValue(value=semester_hint)))
    return Filter(must=must, should=should or None)


def retrieve_handover(state: State) -> dict[str, list[dict[str, Any]]]:
    """Hybrid search across the handover document family.

    인수인계 문서군 전체에 하이브리드 검색한다.
    """
    assert "query" in state and "user" in state
    from api.app.rag.embedder import Embedder

    embedded = Embedder().encode_query(state["query"])
    flt = build_handover_filter(state["user"], state.get("semester_hint"))
    hits = hybrid_search(embedded.dense, embedded.sparse, flt, settings.retrieve_limit)
    return {"candidates": [{"payload": h.payload, "score": h.score} for h in hits]}
