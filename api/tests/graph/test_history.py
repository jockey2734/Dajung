"""Bounded chat-history formatting for graph prompts.

그래프 프롬프트용 제한 대화 기록 포맷 테스트.
"""

from __future__ import annotations

import pytest

from api.app.core.config import settings
from api.app.graph.history import (
    format_history,
    latest_user_question,
    prepend_history,
    truncate_history,
)


def test_truncate_history_keeps_newest_message_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "history_max_messages", 2)
    history = [
        {"role": "user", "content": "oldest"},
        {"role": "assistant", "content": "middle"},
        {"role": "user", "content": "newest"},
    ]

    assert truncate_history(history) == history[-2:]


def test_truncate_history_limits_each_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "history_message_max_chars", 5)

    assert truncate_history([{"role": "user", "content": "abcdef"}]) == [
        {"role": "user", "content": "abcd…"}
    ]


def test_truncate_history_drops_oldest_for_total_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "history_total_max_chars", 7)
    history = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "newest"},
    ]

    assert truncate_history(history) == [history[-1]]


def test_format_history_labels_roles_and_marks_context_only() -> None:
    block = format_history(
        [
            {"role": "user", "content": "앞 질문"},
            {"role": "assistant", "content": "앞 답변"},
        ]
    )

    assert block.startswith("<이전 대화>\n")
    assert "이전 대화는 맥락 참고용 — 자료 인용 규칙은 그대로 적용" in block
    assert "사용자: 앞 질문" in block
    assert "다정 AI: 앞 답변" in block
    assert block.endswith("</이전 대화>")
    assert prepend_history("질문: 현재", []) == "질문: 현재"
    assert format_history([]) == ""


def test_latest_user_question_returns_only_newest_user_on_one_line() -> None:
    history = [
        {"role": "user", "content": "첫 질문"},
        {"role": "assistant", "content": "중간 답변"},
        {"role": "user", "content": "직전\n질문"},
        {"role": "assistant", "content": "마지막 답변"},
    ]

    assert latest_user_question(history) == "직전 질문"
    assert latest_user_question([{"role": "assistant", "content": "답변"}]) is None
