"""Consent offer and direct web/plain generation nodes."""

from __future__ import annotations

from typing import Any

import pytest

from api.app.core.config import settings
from api.app.graph.nodes import plain_generate as plain_mod
from api.app.graph.nodes import web_generate as web_mod
from api.app.graph.nodes.offer_web import OFFER_WEB_MESSAGE, offer_web_node
from api.app.graph.state import State


def _state() -> State:
    return {
        "query": "직전 질문을 이어서 알려줘",
        "user": {"id": "staff-1", "role": "staff"},
        "user_memory": "- 현재 역할: 총무",
        "history": [{"role": "user", "content": "이전 질문"}],
        "candidates": [
            {
                "payload": {
                    "restricted": True,
                    "text": "RESTRICTED-CONTEXT-MUST-NOT-LEAK",
                }
            }
        ],
        "reranked": [
            {
                "payload": {
                    "restricted": True,
                    "text": "RESTRICTED-RERANKED-MUST-NOT-LEAK",
                }
            }
        ],
    }


def test_offer_web_is_deterministic_and_terminal_payload() -> None:
    out = offer_web_node({"query": "질문"})
    assert out == {
        "answer": OFFER_WEB_MESSAGE,
        "model_used": "none",
        "offer": "web_search",
        "citations": [],
    }
    assert OFFER_WEB_MESSAGE == "문서 검색에 실패했습니다. 웹 검색을 시도해보시겠습니까?"


def test_web_generate_uses_history_memory_and_never_restricted_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_complete(**kwargs: Any) -> tuple[str, list[dict[str, str]]]:
        captured.update(kwargs)
        return "공개 웹 답변", [{"kind": "web", "title": "출처", "url": "https://example.test"}]

    monkeypatch.setattr(web_mod, "complete_with_web_search", fake_complete)
    out = web_mod.web_generate_node(_state())

    assert out["answer"].splitlines()[0] == "(웹 검색 결과 — 동아리 내부 자료 아님)"
    assert out["citations"][0]["kind"] == "web"
    assert out["model_used"] == settings.model_sonnet
    assert captured["max_uses"] == settings.web_search_max_uses
    assert "<이전 대화>" in captured["user_text"]
    assert "이전 질문" in captured["user_text"]
    system_text = "\n".join(block["text"] for block in captured["system_blocks"])
    assert "현재 역할: 총무" in system_text
    assert "RESTRICTED-CONTEXT-MUST-NOT-LEAK" not in captured["user_text"]
    assert "RESTRICTED-RERANKED-MUST-NOT-LEAK" not in captured["user_text"]


def test_plain_generate_has_no_citations_or_retrieval_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_complete(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "일반 지식 답변"

    monkeypatch.setattr(plain_mod, "complete", fake_complete)
    out = plain_mod.plain_generate_node(_state())

    assert out["answer"].splitlines()[0] == "(동아리 자료·웹 근거 없음 — 일반 지식 답변)"
    assert out["citations"] == []
    assert out["model_used"] == settings.model_sonnet
    assert "<이전 대화>" in captured["user_text"]
    system_text = "\n".join(block["text"] for block in captured["system_blocks"])
    assert "현재 역할: 총무" in system_text
    assert "동아리 내부 사실" in system_text
    assert "RESTRICTED-CONTEXT-MUST-NOT-LEAK" not in captured["user_text"]
    assert "RESTRICTED-RERANKED-MUST-NOT-LEAK" not in captured["user_text"]
