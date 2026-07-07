"""Serial ask pipeline for the CLI — embed → search → rerank → generate → cite.

CLI용 직렬 ask 파이프라인 — 임베딩 → 검색 → 리랭크 → 생성 → 인용.
Graph-based routing replaces the keyword shortcut in feat/cl-graph-core.
그래프 라우팅은 feat/cl-graph-core에서 키워드 지름길을 대체한다.
"""

from __future__ import annotations

import json as jsonlib
import re
from typing import Any

from api.app.core.config import settings
from api.app.core.logging import get_logger
from api.app.llm.anthropic_client import answer_system_blocks, complete
from api.app.rag.qdrant_store import build_permission_filter, hybrid_search
from api.app.rag.reranker import rerank

log = get_logger(__name__)

_HANDOVER_HINT = re.compile(r"인수인계|물려받|신임|처음 맡")
_MARKER = re.compile(r"\[(\d+)\]")

_HANDOVER_FORMAT = (
    "다음 4개 섹션으로 답하라: ## 해야 할 일 / ## 주의할 일 / "
    "## 확인할 문서 / ## 사람에게 확인할 부분\n"
    "각 항목은 불릿으로, 자료 근거 있는 항목엔 [번호] 마커."
)


def pick_route(question: str, forced: str) -> str:
    """Serial-mode route: forced flag or keyword shortcut (no Ollama yet).

    직렬 모드 라우팅: 강제 플래그 또는 키워드 지름길 (Ollama는 아직).
    """
    if forced in ("knowledge", "handover"):
        return forced
    return "handover" if _HANDOVER_HINT.search(question) else "knowledge"


def pick_model(route: str, question: str, n_hits: int) -> str:
    """Simple model split (Dajung.md §8.15.4) — no cleverness allowed.

    단순 모델 분기 (Dajung.md §8.15.4) — 더 정교화 금지.
    """
    if route == "handover":
        return settings.model_sonnet
    if n_hits >= 3 and len(question) > 50:
        return settings.model_sonnet
    return settings.model_haiku


def build_context(reranked: list[dict[str, Any]]) -> str:
    parts = [
        f"[{i + 1}] {c['payload']['context_header']}\n{c['payload']['text']}"
        for i, c in enumerate(reranked)
    ]
    return "\n\n".join(parts)


def citations_for(answer: str, reranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map [n] markers to sources, in first-appearance order.

    [n] 마커를 등장 순서대로 출처에 매핑한다.
    """
    seen: list[int] = []
    for m in _MARKER.finditer(answer):
        n = int(m.group(1))
        if 1 <= n <= len(reranked) and n not in seen:
            seen.append(n)
    out = []
    for n in seen:
        p = reranked[n - 1]["payload"]
        out.append(
            {
                "marker": n,
                "source_file": p.get("source_file", ""),
                "locator": p.get("locator", ""),
                "category": p.get("category", ""),
                "semester": p.get("semester"),
                "snippet": str(p.get("text", ""))[:120],
            }
        )
    return out


def render(answer: str, route: str, citations: list[dict[str, Any]]) -> str:
    """Terminal output format (Dajung.md §8.15.7).

    터미널 출력 포맷 (Dajung.md §8.15.7).
    """
    lines = [answer]
    if citations:
        lines += ["", "―― 출처 ――"]
        for c in citations:
            semester = c["semester"] or "학기 미상"
            lines.append(
                f"[{c['marker']}] {c['source_file']} · {c['category'] or '미분류'}"
                f" · {semester} · {c['locator']}"
            )
    lines += ["", f"(route: {route})"]
    return "\n".join(lines)


def run_ask_graph(
    question: str,
    user: dict[str, str],
    route: str = "auto",
    json_out: bool = False,
    top_k: int = 0,
) -> str:
    """Graph-backed answer for `dajung ask` (feat/cl-integrate).

    `dajung ask`용 그래프 경유 답변 (feat/cl-integrate).
    """
    import asyncio
    import uuid

    from api.app.graph.graph import get_app
    from api.app.graph.state import Route, State
    from api.app.rag.qdrant_store import get_client

    # Fast fail before loading heavy models (same UX as the serial path).
    # 무거운 모델 로드 전 빠른 실패 (직렬 경로와 동일한 UX).
    if not get_client().collection_exists(settings.collection):
        return f"컬렉션 '{settings.collection}' 없음 — 먼저 `dajung ingest`를 실행하세요."

    state: State = {"query": question, "user": user}
    if route in ("knowledge", "handover"):
        state["route"] = Route(f"{route}_query")

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    final = asyncio.run(get_app().ainvoke(state, config))

    citations = final.get("citations", [])
    if top_k > 0:
        citations = [c for c in citations if c["marker"] <= top_k]
    picked = str(final.get("route", "knowledge_query")).replace("Route.", "")

    if json_out:
        return jsonlib.dumps(
            {
                "answer": final.get("answer", ""),
                "route": picked,
                "model": final.get("model_used", ""),
                "citations": citations,
            },
            ensure_ascii=False,
            indent=1,
        )
    return render(final.get("answer", ""), picked, citations)


def run_ask(
    question: str,
    user: dict[str, str],
    route: str = "auto",
    json_out: bool = False,
    top_k: int = 0,
) -> str:
    """Serial RAG answer — kept as a graph-bypass debug path.

    직렬 RAG 답변 — 그래프 우회 디버그 경로로 유지.
    """
    from api.app.rag.qdrant_store import get_client

    # Cheap reachability/collection check BEFORE loading the heavy embedder.
    # 무거운 임베더를 올리기 전에 값싼 연결·컬렉션 확인부터.
    if not get_client().collection_exists(settings.collection):
        return f"컬렉션 '{settings.collection}' 없음 — 먼저 `dajung ingest`를 실행하세요."

    from api.app.rag.embedder import Embedder

    picked = pick_route(question, route)
    embedded = Embedder().encode_query(question)
    flt = build_permission_filter(user)
    hits = hybrid_search(embedded.dense, embedded.sparse, flt, settings.retrieve_limit)
    candidates = [{"payload": h.payload, "score": h.score} for h in hits]
    reranked = rerank(question, candidates)
    if top_k > 0:
        reranked = reranked[:top_k]
    log.info("ask", route=picked, hits=len(hits), reranked=len(reranked))

    if not reranked:
        answer = "관련 자료를 찾지 못했습니다. 인덱싱된 자료가 있는지 `dajung stats`로 확인하세요."
        citations: list[dict[str, Any]] = []
        model = "none"
    else:
        model = pick_model(picked, question, len(reranked))
        user_text = f"질문: {question}\n\n자료:\n{build_context(reranked)}"
        if picked == "handover":
            user_text = f"{_HANDOVER_FORMAT}\n\n{user_text}"
        answer = complete(
            model=model,
            system_blocks=answer_system_blocks(),
            user_text=user_text,
            max_tokens=settings.max_tokens_generate,
        )
        citations = citations_for(answer, reranked)

    if json_out:
        return jsonlib.dumps(
            {"answer": answer, "route": picked, "model": model, "citations": citations},
            ensure_ascii=False,
            indent=1,
        )
    return render(answer, picked, citations)
