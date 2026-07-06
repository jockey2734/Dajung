"""Graph assembly — compiles and wires the expected nodes (Dajung.md §9).

그래프 조립 — 기대한 노드들이 연결·컴파일되는지 (Dajung.md §9).
"""

from __future__ import annotations

from api.app.graph.graph import build_graph


def test_graph_compiles_with_mvp1_nodes() -> None:
    app = build_graph()
    nodes = set(app.get_graph().nodes)
    expected = {
        "router",
        "retrieve_knowledge",
        "retrieve_handover",
        "permission",
        "rerank",
        "generate",
        "generate_handover",
        "clarify",
    }
    assert expected <= nodes
    # judge must NOT exist (ADR-012 — deferred to MVP4+).
    # judge는 존재하면 안 된다 (ADR-012 — MVP4+ 연기).
    assert "judge" not in nodes


def test_graph_edges_route_correctly() -> None:
    app = build_graph()
    edges = {(e.source, e.target) for e in app.get_graph().edges}
    assert ("retrieve_knowledge", "permission") in edges
    assert ("retrieve_handover", "permission") in edges
    assert ("permission", "rerank") in edges
