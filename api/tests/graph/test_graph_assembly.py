"""Graph assembly — compiles and wires the expected nodes (Dajung.md §9).

그래프 조립 — 기대한 노드들이 연결·컴파일되는지 (Dajung.md §9).
"""

from __future__ import annotations

from typing import Any

import pytest

from api.app.graph import graph as graph_mod
from api.app.graph.graph import build_graph, route_graph_entry
from api.app.graph.nodes import web_generate as web_mod


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
        "cite",
        "offer_web",
        "web_generate",
        "plain_generate",
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
    assert ("router", "clarify") in edges
    assert ("generate", "cite") in edges
    assert ("generate_handover", "cite") in edges
    assert ("offer_web", "__end__") in edges
    assert ("web_generate", "__end__") in edges
    assert ("plain_generate", "__end__") in edges


def test_graph_entry_routes_modes_without_retrieval() -> None:
    assert route_graph_entry({"query": "q"}) == "router"
    assert route_graph_entry({"query": "q", "mode": "rag"}) == "router"
    assert route_graph_entry({"query": "q", "mode": "web"}) == "web_generate"
    assert route_graph_entry({"query": "q", "mode": "plain"}) == "plain_generate"


async def test_web_mode_compiled_graph_never_calls_rag_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(state: Any) -> dict[str, Any]:
        raise AssertionError("RAG node must not run in web mode")

    def fake_web_complete(**kwargs: Any) -> tuple[str, list[dict[str, str]]]:
        return "공개 답변", [{"kind": "web", "title": "공식", "url": "https://example.test"}]

    monkeypatch.setattr(graph_mod, "router_node", forbidden)
    monkeypatch.setattr(graph_mod, "retrieve_knowledge", forbidden)
    monkeypatch.setattr(graph_mod, "retrieve_handover", forbidden)
    monkeypatch.setattr(graph_mod, "permission_node", forbidden)
    monkeypatch.setattr(web_mod, "complete_with_web_search", fake_web_complete)
    app = graph_mod.build_graph()

    out = await app.ainvoke(
        {
            "query": "질문",
            "mode": "web",
            "user": {"id": "staff-1", "role": "staff"},
            "candidates": [{"payload": {"restricted": True, "text": "RESTRICTED-MUST-NOT-LEAK"}}],
        },
        {"configurable": {"thread_id": "s26-web-entry"}},
    )

    assert out["answer"].startswith("(웹 검색 결과 — 동아리 내부 자료 아님)\n")
    assert out["citations"] == [{"kind": "web", "title": "공식", "url": "https://example.test"}]
