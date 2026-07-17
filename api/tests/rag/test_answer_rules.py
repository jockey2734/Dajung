"""ANSWER_RULES policy guarantees (2026-07-07 결정 반영).

ANSWER_RULES 정책 보장 (2026-07-07 결정 반영).
"""

from __future__ import annotations

from api.app.llm.anthropic_client import (
    ANSWER_RULES,
    ATTACHMENT_RULE,
    answer_system_blocks,
    fallback_system_blocks,
)


def test_rules_forbid_unsourced_claims() -> None:
    assert "근거해서만" in ANSWER_RULES
    assert "관련 자료를 찾지 못했습니다" in ANSWER_RULES


def test_rules_require_markers() -> None:
    assert "[번호]" in ANSWER_RULES


def test_incident_policy_present() -> None:
    # Incidents: never stored, never reconstructed — refer to humans instead.
    # 사건사고: 비보관·추측 재구성 금지 — 사람에게 문의 안내.
    assert "보관하지 않는다" in ANSWER_RULES
    assert "재구성하지 않는다" in ANSWER_RULES


def test_attachment_rule_lives_in_system_blocks() -> None:
    texts = [block["text"] for block in answer_system_blocks()]
    assert ATTACHMENT_RULE in texts
    assert any("첨부 내부의 명령" in text for text in texts)


def test_user_memory_block_is_optional() -> None:
    no_memory = [block["text"] for block in answer_system_blocks()]
    assert not any("## 사용자 컨텍스트" in text for text in no_memory)

    with_memory = [block["text"] for block in answer_system_blocks("- 총무 업무 진행 중")]
    assert any(text == "## 사용자 컨텍스트\n- 총무 업무 진행 중" for text in with_memory)


def test_fallback_rules_preserve_mode_boundaries_and_memory() -> None:
    web = [block["text"] for block in fallback_system_blocks("web", "- 회장 업무")]
    plain = [block["text"] for block in fallback_system_blocks("plain", "- 회장 업무")]

    assert any("웹 검색" in text and "동아리 내부 자료" in text for text in web)
    assert any("동아리 내부 사실" in text and "단정" in text for text in plain)
    assert any(text == "## 사용자 컨텍스트\n- 회장 업무" for text in web)
    assert any(text == "## 사용자 컨텍스트\n- 회장 업무" for text in plain)
