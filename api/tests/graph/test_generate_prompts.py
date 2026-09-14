"""Generate-node prompt composition tests."""

from __future__ import annotations

import re
from typing import Any

import pytest

from api.app.graph.nodes import generate as generate_mod
from api.app.graph.nodes import generate_handover as handover_mod
from api.app.llm import anthropic_client as anthropic_mod
from api.app.llm.anthropic_client import (
    ATTACHMENT_RULE,
    answer_system_blocks,
    fallback_system_blocks,
)


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


def test_date_block_is_last_uncached_and_preserves_cache_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_context = "오늘: 2026년 7월 26일 (일) · 현재 학기: 2026-1 · 여름방학"
    monkeypatch.setattr(anthropic_mod, "date_context", lambda: fixed_context)

    block_sets = [
        answer_system_blocks(),
        answer_system_blocks("- 총무 업무"),
        fallback_system_blocks("web", "- 총무 업무"),
        fallback_system_blocks("plain", "- 총무 업무"),
    ]
    for blocks in block_sets:
        assert blocks[-1]["text"].startswith(f"## 현재 시각\n{fixed_context}\n")
        assert "cache_control" not in blocks[-1]
        assert sum("cache_control" in block for block in blocks) <= 4
        memory_indexes = [
            index
            for index, block in enumerate(blocks)
            if block["text"].startswith("## 사용자 컨텍스트")
        ]
        if memory_indexes:
            assert memory_indexes == [len(blocks) - 2]
        assert "상대 표현" in blocks[-1]["text"]
        assert "자료의 학기와 현재 학기가 다르면" in blocks[-1]["text"]
        assert "미래 일정은 단정하지 않고" in blocks[-1]["text"]


# webapp-spec S30-5: the FX block sits between the question and the 자료 material,
# carries no [n] marker, and rule 7 tells the model it is not a citation source.
# webapp-spec S30-5: 환율 블록은 질문과 자료 사이에 놓이고, [n] 마커가 없으며,
# 규칙 7이 모델에게 인용 출처가 아님을 알린다.
FX_BLOCK = "## 환율 (한국수출입은행 매매기준율, 2026-07-24 고시 기준)\n- 1 CNY = 191.24원"
RULE_7 = (
    "7. 환율 블록은 시스템이 제공한 참고 정보이며 인용 출처가 아니다. [번호] 마커를 붙이지 않는다."
)


def test_generate_node_places_fx_block_before_material_without_marker(
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
    generate_mod.generate_node(
        {"query": "대홍포 얼마야", "reranked": _reranked(), "fx_block": FX_BLOCK}
    )

    text = captured["user_text"]
    assert text.index("질문: 대홍포 얼마야") < text.index(FX_BLOCK) < text.index("자료:\n[1] ")
    assert re.search(r"\[\d+\][^\n]*## 환율", text) is None
    assert any(RULE_7 in block_text for block_text in captured["texts"])


def test_generate_handover_places_fx_block_before_material(
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
    handover_mod.generate_handover(
        {
            "query": "타오바오 공구 인수인계",
            "reranked": _reranked(),
            "role_hint": "총무",
            "fx_block": FX_BLOCK,
        }
    )

    text = captured["user_text"]
    question_at = text.index("질문: 타오바오 공구 인수인계")
    assert question_at < text.index(FX_BLOCK) < text.index("자료:\n[1] ")
    assert re.search(r"\[\d+\][^\n]*## 환율", text) is None
    assert any(RULE_7 in block_text for block_text in captured["texts"])


def test_generate_nodes_omit_fx_block_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert "## 환율" not in captured["user_text"]

    monkeypatch.setattr(handover_mod, "complete", fake_complete)
    handover_mod.generate_handover({"query": "인수인계 질문", "reranked": _reranked()})
    assert "## 환율" not in captured["user_text"]
