"""MVP1 graph assembly (Dajung.md §8.16, system-design §9.2).

MVP1 그래프 조립 (Dajung.md §8.16, system-design §9.2).
Cite node joins in feat/ag-cite; until then generate → END.
cite 노드는 feat/ag-cite에서 합류. 그 전까지 generate → END.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from api.app.graph.nodes.cite import cite_node
from api.app.graph.nodes.clarify import clarify_node
from api.app.graph.nodes.fx_context import fx_context_node
from api.app.graph.nodes.generate import generate_node
from api.app.graph.nodes.generate_handover import generate_handover
from api.app.graph.nodes.offer_web import offer_web_node
from api.app.graph.nodes.permission import permission_node
from api.app.graph.nodes.plain_generate import plain_generate_node
from api.app.graph.nodes.rerank import rerank_node, route_after_rerank
from api.app.graph.nodes.retrieve_handover import retrieve_handover
from api.app.graph.nodes.retrieve_knowledge import retrieve_knowledge
from api.app.graph.nodes.router import router_node
from api.app.graph.nodes.web_generate import web_generate_node
from api.app.graph.state import Route, State

_APP: Any = None


def route_graph_entry(state: State) -> str:
    """Select RAG, web, or plain entry without touching retrieval.

    검색을 실행하지 않고 RAG, 웹, 일반 답변 진입점을 선택한다.
    """
    mode = state.get("mode", "rag")
    return {"web": "web_generate", "plain": "plain_generate"}.get(mode, "router")


def build_graph() -> Any:
    """Assemble and compile the MVP1 graph.

    MVP1 그래프를 조립·컴파일한다.
    """
    graph = StateGraph(State)

    graph.add_node("router", router_node)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("retrieve_handover", retrieve_handover)
    graph.add_node("permission", permission_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("generate", generate_node)
    graph.add_node("generate_handover", generate_handover)
    graph.add_node("clarify", clarify_node)
    graph.add_node("cite", cite_node)
    graph.add_node("offer_web", offer_web_node)
    graph.add_node("web_generate", web_generate_node)
    graph.add_node("plain_generate", plain_generate_node)
    graph.add_node("fx_context", fx_context_node)

    graph.set_conditional_entry_point(
        route_graph_entry,
        {
            "router": "router",
            "web_generate": "web_generate",
            "plain_generate": "plain_generate",
        },
    )
    graph.add_conditional_edges(
        "router",
        lambda s: s["route"],
        {
            Route.KNOWLEDGE_QUERY: "retrieve_knowledge",
            Route.HANDOVER_QUERY: "retrieve_handover",
            Route.UNCLEAR: "clarify",
        },
    )

    graph.add_edge("retrieve_knowledge", "permission")
    graph.add_edge("retrieve_handover", "permission")
    graph.add_edge("permission", "rerank")

    # Generate paths pass through fx_context first; retry and offer_web do not
    # (no material means no use for a rate). route_after is rerank's own decision.
    # 생성 경로는 fx_context를 먼저 거치고, 재시도·offer_web은 거치지 않는다
    # (자료가 없으면 환율도 쓸모없다). route_after는 rerank가 내린 결정 그대로다.
    graph.add_conditional_edges(
        "rerank",
        route_after_rerank,
        {
            "generate": "fx_context",
            "generate_handover": "fx_context",
            "retrieve_knowledge": "retrieve_knowledge",
            "retrieve_handover": "retrieve_handover",
            "offer_web": "offer_web",
        },
    )
    graph.add_conditional_edges(
        "fx_context",
        lambda s: s["route_after"],
        {
            "generate": "generate",
            "generate_handover": "generate_handover",
        },
    )

    graph.add_edge("generate", "cite")
    graph.add_edge("generate_handover", "cite")
    graph.add_edge("cite", END)
    graph.add_edge("clarify", END)
    graph.add_edge("offer_web", END)
    graph.add_edge("web_generate", END)
    graph.add_edge("plain_generate", END)

    # PostgresSaver replaces MemorySaver in the serving phase (P3).
    # 서빙 단계(P3)에서 MemorySaver를 PostgresSaver로 교체한다.
    return graph.compile(checkpointer=MemorySaver())


def get_app() -> Any:
    """Module-level lazy singleton of the compiled graph.

    컴파일된 그래프의 모듈 레벨 지연 싱글턴.
    """
    global _APP
    if _APP is None:
        _APP = build_graph()
    return _APP
