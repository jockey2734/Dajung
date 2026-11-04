"""Per-route effort and refusal handling in the generate nodes (Sonnet/Opus 5.5).

생성 노드의 경로별 effort와 거절 처리 (Sonnet/Opus 5.5).
"""

from __future__ import annotations

from typing import Any

import pytest

from api.app.core.config import settings
from api.app.graph.nodes import generate as generate_mod
from api.app.graph.nodes import generate_handover as handover_mod
from api.app.graph.nodes import plain_generate as plain_mod
from api.app.graph.nodes import web_generate as web_mod
from api.app.graph.state import State
from api.app.llm.anthropic_client import REFUSAL_ANSWER, ModelRefusalError
from api.app.rag.answer import pick_effort


def _reranked(n: int = 1) -> list[dict[str, Any]]:
    return [
        {
            "payload": {
                "context_header": "[문서: guide.md]",
                "text": "본문",
                "source_file": "guide.md",
                "locator": f"p.{i + 1}",
                "category": "테스트",
                "semester": "2025-1",
            },
            "rerank_score": 0.9,
        }
        for i in range(n)
    ]


def _refuse(**_: Any) -> Any:
    raise ModelRefusalError("general_harms")


def test_pick_effort_is_complex_for_sonnet_and_none_for_haiku() -> None:
    assert pick_effort(settings.model_sonnet) == settings.sonnet_effort_complex
    assert pick_effort(settings.model_haiku) is None


def test_generate_sends_complex_effort_when_sonnet_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_complete(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "답변 [1]"

    monkeypatch.setattr(generate_mod, "complete", fake_complete)
    # Long question with 3+ hits routes to Sonnet (pick_model).
    # 3건 이상 히트 + 긴 질문은 Sonnet으로 간다 (pick_model).
    long_question = "가" * 60
    generate_mod.generate_node({"query": long_question, "reranked": _reranked(3)})
    assert captured["model"] == settings.model_sonnet
    assert captured["effort"] == settings.sonnet_effort_complex


def test_generate_sends_no_effort_when_haiku_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_complete(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "답변 [1]"

    monkeypatch.setattr(generate_mod, "complete", fake_complete)
    generate_mod.generate_node({"query": "짧은 질문", "reranked": _reranked(1)})
    assert captured["model"] == settings.model_haiku
    assert captured["effort"] is None


def test_handover_sends_complex_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_complete(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "## 해야 할 일\n- 항목 [1]"

    monkeypatch.setattr(handover_mod, "complete", fake_complete)
    handover_mod.generate_handover({"query": "신임 총무 할 일", "reranked": _reranked(1)})
    assert captured["effort"] == settings.sonnet_effort_complex


def test_plain_and_web_send_other_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_plain(**kwargs: Any) -> str:
        captured["plain"] = kwargs["effort"]
        return "일반 답변"

    def fake_web(**kwargs: Any) -> tuple[str, list[dict[str, str]]]:
        captured["web"] = kwargs["effort"]
        return "웹 답변", []

    monkeypatch.setattr(plain_mod, "complete", fake_plain)
    monkeypatch.setattr(web_mod, "complete_with_web_search", fake_web)
    state: State = {"query": "질문"}
    plain_mod.plain_generate_node(state)
    web_mod.web_generate_node(state)
    assert captured == {"plain": settings.sonnet_effort_other, "web": settings.sonnet_effort_other}


def test_refusal_becomes_fixed_message_in_every_node(monkeypatch: pytest.MonkeyPatch) -> None:
    # A declined request must not reach the user as an empty answer.
    # 거절된 요청이 빈 답변으로 사용자에게 가면 안 된다.
    monkeypatch.setattr(generate_mod, "complete", _refuse)
    monkeypatch.setattr(handover_mod, "complete", _refuse)
    monkeypatch.setattr(plain_mod, "complete", _refuse)
    monkeypatch.setattr(web_mod, "complete_with_web_search", _refuse)

    knowledge = generate_mod.generate_node({"query": "질문", "reranked": _reranked(1)})
    handover = handover_mod.generate_handover({"query": "질문", "reranked": _reranked(1)})
    plain = plain_mod.plain_generate_node({"query": "질문"})
    web = web_mod.web_generate_node({"query": "질문"})

    for out in (knowledge, handover, plain, web):
        assert out["answer"] == REFUSAL_ANSWER
    assert plain["citations"] == [] and web["citations"] == []
