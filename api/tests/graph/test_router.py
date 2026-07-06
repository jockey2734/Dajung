"""Router node cases — Ollama mocked, fully offline (Dajung.md §9).

라우터 노드 케이스 — Ollama 모킹, 완전 오프라인 (Dajung.md §9).
"""

from __future__ import annotations

import pytest

from api.app.graph.nodes import router as router_mod
from api.app.graph.state import Route, State


def _state(query: str) -> State:
    return {"query": query, "user": {"id": "u", "email": "e", "role": "staff"}}


async def _fake_chat_factory(response: str | Exception):  # type: ignore[no-untyped-def]
    async def fake_chat(*args: object, **kwargs: object) -> str:
        if isinstance(response, Exception):
            raise response
        return response

    return fake_chat


async def test_valid_json_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = (
        '{"route": "handover_query", "role_hint": "president",'
        ' "semester_hint": "2025-1", "topic_hint": null}'
    )
    monkeypatch.setattr(router_mod._client, "chat", await _fake_chat_factory(raw))
    out = await router_mod.router_node(_state("신임 회장 인수인계"))
    assert out["route"] == Route.HANDOVER_QUERY
    assert out["role_hint"] == "president"
    assert out["semester_hint"] == "2025-1"
    assert out["retries"] == 0


async def test_broken_json_defaults_knowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_mod._client, "chat", await _fake_chat_factory("응 나는 JSON 못해"))
    out = await router_mod.router_node(_state("아무 질문"))
    assert out["route"] == Route.KNOWLEDGE_QUERY


async def test_json_blob_salvaged(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = '설명: 아래처럼요\n{"route": "unclear"}\n끝!'
    monkeypatch.setattr(router_mod._client, "chat", await _fake_chat_factory(raw))
    out = await router_mod.router_node(_state("음"))
    assert out["route"] == Route.UNCLEAR


async def test_invalid_route_value_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        router_mod._client, "chat", await _fake_chat_factory('{"route": "budget_query"}')
    )
    out = await router_mod.router_node(_state("예산?"))
    # budget_query is MVP2 — unknown values fall back to the default route.
    # budget_query는 MVP2 — 미지 값은 기본 라우트로 처리한다.
    assert out["route"] == Route.KNOWLEDGE_QUERY


async def test_ollama_down_keyword_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        router_mod._client, "chat", await _fake_chat_factory(ConnectionError("down"))
    )
    out = await router_mod.router_node(_state("신임 회장이 처음 맡으면?"))
    assert out["route"] == Route.HANDOVER_QUERY
    out = await router_mod.router_node(_state("개완 우리는 법"))
    assert out["route"] == Route.KNOWLEDGE_QUERY


def test_parse_router_json_pure() -> None:
    assert router_mod.parse_router_json('{"route": "unclear"}')["route"] == "unclear"
    assert router_mod.parse_router_json("garbage") == {}
