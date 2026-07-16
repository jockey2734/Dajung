"""Bounded same-session history for graph prompts.

그래프 프롬프트용으로 제한한 같은 세션 대화 기록.
"""

from __future__ import annotations

from api.app.core.config import settings

_CONTEXT_NOTE = "이전 대화는 맥락 참고용 — 자료 인용 규칙은 그대로 적용."
_ROLE_LABELS = {"user": "사용자", "assistant": "다정 AI"}


def _truncate_content(content: str) -> str:
    max_chars = settings.history_message_max_chars
    if len(content) <= max_chars:
        return content
    if max_chars <= 0:
        return ""
    if max_chars == 1:
        return "…"
    return f"{content[: max_chars - 1]}…"


def truncate_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply the newest-message, per-message, and total-content limits.

    최신 메시지 수, 메시지별 길이, 전체 내용 길이 상한을 적용한다.
    """
    if settings.history_max_messages <= 0:
        return []
    bounded = [
        {"role": item["role"], "content": _truncate_content(item["content"])}
        for item in history[-settings.history_max_messages :]
    ]
    total_chars = sum(len(item["content"]) for item in bounded)
    while bounded and total_chars > settings.history_total_max_chars:
        total_chars -= len(bounded.pop(0)["content"])
    return bounded


def format_history(history: list[dict[str, str]]) -> str:
    """Render bounded history as context that is explicitly not a citation source.

    제한된 기록을 인용 출처가 아닌 맥락 블록으로 렌더링한다.
    """
    bounded = truncate_history(history)
    if not bounded:
        return ""
    lines = ["<이전 대화>", _CONTEXT_NOTE]
    lines.extend(
        f"{_ROLE_LABELS[item['role']]}: {item['content']}"
        for item in bounded
        if item["role"] in _ROLE_LABELS
    )
    lines.append("</이전 대화>")
    return "\n".join(lines)


def prepend_history(text: str, history: list[dict[str, str]]) -> str:
    """Prepend the optional history block to current-turn prompt text.

    선택적인 기록 블록을 현재 턴 프롬프트 앞에 붙인다.
    """
    block = format_history(history)
    return f"{block}\n\n{text}" if block else text


def latest_user_question(history: list[dict[str, str]]) -> str | None:
    """Return the newest prior user message collapsed to one line.

    가장 최근의 이전 사용자 메시지를 한 줄로 합쳐 반환한다.
    """
    for item in reversed(truncate_history(history)):
        if item["role"] == "user":
            question = " ".join(item["content"].split())
            return question or None
    return None
