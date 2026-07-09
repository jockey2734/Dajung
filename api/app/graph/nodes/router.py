"""Router node — 3-way classification via local Ollama (Dajung.md §8.14).

라우터 노드 — 로컬 Ollama 3분류 (Dajung.md §8.14).
Fallback ladder: JSON parse retry → keyword heuristic on any Ollama failure.
폴백 사다리: JSON 파싱 재시도 → Ollama 실패 시 키워드 휴리스틱.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from api.app.core.config import settings
from api.app.core.logging import get_logger
from api.app.graph.state import Route, State
from api.app.llm.ollama_client import OllamaClient

log = get_logger(__name__)

# One request at a time on the single 8GB GPU (ARCHITECTURE.md §7).
# 단일 8GB GPU라 한 번에 한 요청만 (ARCHITECTURE.md §7).
_gpu_lock = asyncio.Lock()

_client = OllamaClient(host=settings.ollama_base_url)

_JSON_BLOB = re.compile(r"\{.*\}", re.DOTALL)
_HANDOVER_HINT = re.compile(r"인수인계|물려받|신임|처음 맡")

ROUTER_PROMPT = """다음 사용자 질문을 분류하고, 인수인계 질문이면 힌트를 추출하세요.
JSON 형식으로 응답:
{{"route": "knowledge_query" | "handover_query" | "unclear",
 "role_hint": null | "president" | "treasurer" | "seminar_lead" | "general",
 "semester_hint": null | "YYYY-N",
 "topic_hint": null | "recruitment" | "budget" | "seminar" | "inventory" | "union_document"}}

라우트:
- knowledge_query: 차/커피 지식, 우리는 법, 장비 사용법, 운영 규칙,
  체크리스트 위치, 과거 문서 내용 질의 (기본값)
- handover_query: 직책 인수인계 — "물려받았는데", "신임 회장/총무가 할 일",
  "학기 초에 뭐부터" 류의 다문서 종합 질문
- unclear: 위 둘 다 확신 없음 → 시스템이 되묻는다

질문: {query}
"""


def parse_router_json(raw: str) -> dict[str, Any]:
    """Parse the router JSON; salvage the first {...} blob; else defaults.

    라우터 JSON 파싱. 첫 {...} 블록 구제 시도, 실패 시 기본값.
    """
    for candidate in (raw, *(m.group(0) for m in [_JSON_BLOB.search(raw)] if m)):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    log.warning("router json unparseable, defaulting to knowledge_query")
    return {}


def keyword_route(question: str) -> Route:
    """Offline fallback when Ollama is down (Dajung.md §8.14).

    Ollama 다운 시 오프라인 폴백 (Dajung.md §8.14).
    """
    return Route.HANDOVER_QUERY if _HANDOVER_HINT.search(question) else Route.KNOWLEDGE_QUERY


def _to_route(value: object) -> Route:
    try:
        return Route(str(value))
    except ValueError:
        return Route.KNOWLEDGE_QUERY


async def router_node(state: State) -> dict[str, Any]:
    """Classify the query and extract handover hints.

    질문을 분류하고 인수인계 힌트를 추출한다.
    """
    assert "query" in state
    query = state["query"]

    # CLI --route flag pre-sets the route — skip Ollama entirely (§8.2).
    # CLI --route 플래그가 라우트를 선지정하면 Ollama를 건너뛴다 (§8.2).
    if "route" in state:
        log.info("router", route=str(state["route"]), backend="forced", latency_ms=0)
        return {"route": state["route"], "retries": 0}
    started = time.monotonic()
    backend = "local"

    try:
        async with _gpu_lock:
            raw = await asyncio.wait_for(
                _client.chat(
                    model=settings.router_model,
                    messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
                    format="json",
                ),
                timeout=settings.router_timeout_s,
            )
        data = parse_router_json(raw)
        route = _to_route(data.get("route"))
        hints = {
            "role_hint": data.get("role_hint"),
            "semester_hint": data.get("semester_hint"),
            "topic_hint": data.get("topic_hint"),
        }
    except Exception as exc:
        backend = "keyword"
        route = keyword_route(query)
        hints = {"role_hint": None, "semester_hint": None, "topic_hint": None}
        log.warning("router fallback to keyword", error=str(exc))

    # Latency/backend logging feeds the API-fallback decision (Dajung.md §8.14-a).
    # latency·backend 로그가 API 폴백 활성화 판단의 데이터다 (Dajung.md §8.14-a).
    log.info(
        "router",
        route=str(route),
        backend=backend,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    return {"route": route, "retries": 0, **hints}
