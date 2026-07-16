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
    captured: dict[str, Any] = {}

    def fake_complete(
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
    ) -> str:
        captured["texts"] = [block["text"] for block in system_blocks]
        captured["user_text"] = user_text
        return "답변 [1]"

    monkeypatch.setattr(generate_mod, "complete", fake_complete)
    out = generate_mod.generate_node(
        {
            "query": "현재 질문",
            "reranked": _reranked(),
            "user_memory": "- 총무 업무 진행 중",
            "history": [
                {"role": "user", "content": "앞 질문"},
                {"role": "assistant", "content": "앞 답변"},
            ],
        }
    )

    assert out["answer"] == "답변 [1]"
    assert ATTACHMENT_RULE in captured["texts"]
    assert "## 사용자 컨텍스트\n- 총무 업무 진행 중" in captured["texts"]
    assert "<이전 대화>" in captured["user_text"]
    assert "사용자: 앞 질문" in captured["user_text"]
    assert "다정 AI: 앞 답변" in captured["user_text"]
    assert captured["user_text"].index("</이전 대화>") < captured["user_text"].index(
        "질문: 현재 질문"
    )


def test_generate_handover_injects_memory_and_attachment_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_complete(
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
    ) -> str:
        captured["texts"] = [block["text"] for block in system_blocks]
        captured["user_text"] = user_text
        return "인수인계 답변 [1]"

    monkeypatch.setattr(handover_mod, "complete", fake_complete)
    out = handover_mod.generate_handover(
        {
            "query": "현재 인수인계 질문",
            "reranked": _reranked(),
            "user_memory": "- 회장 인수인계 중",
            "history": [{"role": "user", "content": "직전 역할 질문"}],
        }
    )

    assert out["answer"] == "인수인계 답변 [1]"
    assert ATTACHMENT_RULE in captured["texts"]
    assert "## 사용자 컨텍스트\n- 회장 인수인계 중" in captured["texts"]
    assert captured["user_text"].startswith("<이전 대화>\n")
    assert "사용자: 직전 역할 질문" in captured["user_text"]
    assert captured["user_text"].index("</이전 대화>") < captured["user_text"].index(
        "질문: 현재 인수인계 질문"
    )


def test_generate_node_omits_history_block_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_complete(
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
    ) -> str:
        captured["user_text"] = user_text
        return "답변 [1]"

    monkeypatch.setattr(generate_mod, "complete", fake_complete)
    generate_mod.generate_node({"query": "새 질문", "reranked": _reranked()})

    assert "<이전 대화>" not in captured["user_text"]
