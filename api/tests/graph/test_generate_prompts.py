"""Generate-node prompt composition tests."""

from __future__ import annotations

from typing import Any

import pytest

from api.app.graph.nodes import generate as generate_mod
from api.app.graph.nodes import generate_handover as handover_mod
from api.app.llm.anthropic_client import ATTACHMENT_RULE


def _reranked() -> list[dict[str, Any]]:
    return [
        {
            "payload": {
                "context_header": "[문서: guide.md]",
                "text": "본문",
                "source_file": "guide.md",
                "locator": "p.1",
                "category": "테스트",
                "semester": "2025-1",
            },
            "rerank_score": 0.9,
        }
    ]


def test_generate_node_injects_memory_and_attachment_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, list[str]] = {}

    def fake_complete(
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
    ) -> str:
        captured["texts"] = [block["text"] for block in system_blocks]
        return "답변 [1]"

    monkeypatch.setattr(generate_mod, "complete", fake_complete)
    out = generate_mod.generate_node(
        {"query": "질문", "reranked": _reranked(), "user_memory": "- 총무 업무 진행 중"}
    )

    assert out["answer"] == "답변 [1]"
    assert ATTACHMENT_RULE in captured["texts"]
    assert "## 사용자 컨텍스트\n- 총무 업무 진행 중" in captured["texts"]


def test_generate_handover_injects_memory_and_attachment_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, list[str]] = {}

    def fake_complete(
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
    ) -> str:
        captured["texts"] = [block["text"] for block in system_blocks]
        return "인수인계 답변 [1]"

    monkeypatch.setattr(handover_mod, "complete", fake_complete)
    out = handover_mod.generate_handover(
        {"query": "질문", "reranked": _reranked(), "user_memory": "- 회장 인수인계 중"}
    )

    assert out["answer"] == "인수인계 답변 [1]"
    assert ATTACHMENT_RULE in captured["texts"]
    assert "## 사용자 컨텍스트\n- 회장 인수인계 중" in captured["texts"]
