"""Cite node cases (Dajung.md §9).

cite 노드 케이스 (Dajung.md §9).
"""

from __future__ import annotations

from typing import Any

from api.app.graph.nodes.cite import cite_node, strip_invalid_markers
from api.app.graph.state import State


def _reranked(n: int) -> list[dict[str, Any]]:
    return [
        {
            "payload": {
                "source_file": f"f{i}.md",
                "locator": f"p.{i}",
                "category": "테스트",
                "semester": "2025-1",
                "text": f"본문 {i}",
                "context_header": f"[문서: f{i}.md]",
            },
            "rerank_score": 0.9,
        }
        for i in range(n)
    ]


def test_markers_mapped_in_order() -> None:
    state: State = {"answer": "규칙 확인 [2]. 명단 인계 [1]. 다시 [2].", "reranked": _reranked(3)}
    out = cite_node(state)
    assert [c["marker"] for c in out["citations"]] == [2, 1]
    assert all(c["kind"] == "doc" for c in out["citations"])
    assert out["citations"][0]["source_file"] == "f1.md"


def test_out_of_range_marker_removed() -> None:
    state: State = {"answer": "근거 [1] 그리고 유령 [7].", "reranked": _reranked(2)}
    out = cite_node(state)
    assert "[7]" not in out["answer"]
    assert "[1]" in out["answer"]
    assert [c["marker"] for c in out["citations"]] == [1]


def test_no_markers_empty_citations() -> None:
    state: State = {"answer": "마커 없는 답변.", "reranked": _reranked(2)}
    out = cite_node(state)
    assert out["citations"] == []
    assert out["answer"] == "마커 없는 답변."


def test_empty_reranked_strips_all_markers() -> None:
    state: State = {"answer": "자료 없음인데 [1] 마커가?", "reranked": []}
    out = cite_node(state)
    assert "[1]" not in out["answer"]
    assert out["citations"] == []


def test_strip_helper_pure() -> None:
    assert strip_invalid_markers("[1][2][3]", 2) == "[1][2]"
