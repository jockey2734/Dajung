"""Knowledge retrieval node — hybrid search, no doc_type restriction (§8.15.1).

지식 검색 노드 — 하이브리드 검색, doc_type 제한 없음 (§8.15.1).
"""

from __future__ import annotations

from typing import Any

from api.app.core.config import settings
from api.app.graph.state import State
from api.app.rag.qdrant_store import build_permission_filter, hybrid_search


def retrieve_knowledge(state: State) -> dict[str, list[dict[str, Any]]]:
    """Embed the query and run hybrid search under the permission filter.

    쿼리를 임베딩해 권한 필터 하에 하이브리드 검색한다.
    """
    assert "query" in state and "user" in state
    from api.app.rag.embedder import Embedder

    embedded = Embedder().encode_query(state["query"])
    flt = build_permission_filter(state["user"])
    hits = hybrid_search(embedded.dense, embedded.sparse, flt, settings.retrieve_limit)
    # Normalize to plain dicts — every downstream node speaks dicts only.
    # 평범한 dict로 정규화 — 이후 노드는 dict만 다룬다.
    return {"candidates": [{"payload": h.payload, "score": h.score} for h in hits]}
