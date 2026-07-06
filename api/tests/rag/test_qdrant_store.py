"""Qdrant store — live roundtrip (external) plus pure checks.

Qdrant 스토어 — 라이브 왕복(external) + 순수 검사.
"""

from __future__ import annotations

import pytest

from api.app.rag.qdrant_store import build_permission_filter


def test_filter_is_single_source_of_truth() -> None:
    # Non-owner filters always constrain by restricted/allowed_users keys.
    # 비-owner 필터는 항상 restricted/allowed_users 키로 제한한다.
    flt = build_permission_filter({"id": "u1", "role": "staff"})
    assert flt is not None
    keys = {c.key for c in flt.should}  # type: ignore[union-attr]
    assert keys == {"restricted", "allowed_users"}


@pytest.mark.external
def test_collection_roundtrip() -> None:
    # Requires a live Qdrant at settings.qdrant_url.
    # settings.qdrant_url에 살아 있는 Qdrant 필요.
    from api.app.rag.qdrant_store import (
        collection_stats,
        delete_doc,
        ensure_collection,
        hybrid_search,
        upsert_chunks,
    )

    ensure_collection()
    payload = {
        "doc_id": "test-doc-roundtrip",
        "source_file": "roundtrip.md",
        "doc_type": "misc",
        "restricted": False,
        "allowed_users": [],
        "text": "라운드트립 테스트 본문",
        "context_header": "[문서: roundtrip.md]",
    }
    dense = [0.01] * 1024
    sparse = {1: 0.5, 42: 0.3}
    assert upsert_chunks([payload], [dense], [sparse]) == 1

    hits = hybrid_search(dense, sparse, flt=None, limit=5)
    assert any(
        h.payload is not None and h.payload.get("doc_id") == "test-doc-roundtrip" for h in hits
    )
    assert "chunks:" in collection_stats()
    delete_doc("test-doc-roundtrip")
