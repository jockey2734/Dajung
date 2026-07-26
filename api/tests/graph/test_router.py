"""Router node cases — Ollama mocked, fully offline (Dajung.md §9).

라우터 노드 케이스 — Ollama 모킹, 완전 오프라인 (Dajung.md §9).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from api.app.core.clock import KST
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


async def test_router_prompt_includes_only_latest_user_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def fake_chat(*args: object, **kwargs: object) -> str:
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        captured["prompt"] = messages[0]["content"]
        return '{"route": "knowledge_query"}'

    monkeypatch.setattr(router_mod._client, "chat", fake_chat)
    state = _state("그건 어떻게 해?")
    state["history"] = [
        {"role": "user", "content": "오래된 질문"},
        {"role": "assistant", "content": "직전 답변"},
        {"role": "user", "content": "가장 최근\n질문"},
    ]

    await router_mod.router_node(state)

    assert "직전 질문: 가장 최근 질문" in captured["prompt"]
    assert "오래된 질문" not in captured["prompt"]
    assert "직전 답변" not in captured["prompt"]


async def test_router_prompt_includes_calculated_date_and_semester(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def fake_chat(*args: object, **kwargs: object) -> str:
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        captured["prompt"] = messages[0]["content"]
        return '{"route": "knowledge_query", "semester_hint": "2026-1"}'

    monkeypatch.setattr(router_mod._client, "chat", fake_chat)
    monkeypatch.setattr(
        router_mod,
        "now_kst",
        lambda: datetime(2026, 7, 26, 9, 30, tzinfo=KST),
    )

    await router_mod.router_node(_state("이번 학기 총무 업무"))

    assert "현재: 2026년 7월 26일 (학기 2026-1)" in captured["prompt"]
    assert '"이번 학기"는 2026-1' in captured["prompt"]
    assert '"지난 학기"는 그 직전 학기' in captured["prompt"]


def test_parse_router_json_pure() -> None:
    assert router_mod.parse_router_json('{"route": "unclear"}')["route"] == "unclear"
    assert router_mod.parse_router_json("garbage") == {}
