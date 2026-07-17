"""Anthropic web-search adapter contract with a fake SDK client.

가짜 SDK 클라이언트로 검증하는 Anthropic 웹 검색 어댑터 계약.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from api.app.llm import anthropic_client


def test_web_search_tool_and_citations_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    citation = SimpleNamespace(
        type="web_search_result_location",
        title="공식 안내",
        url="https://example.test/guide",
    )
    duplicate = SimpleNamespace(
        type="web_search_result_location",
        title="중복 제목",
        url="https://example.test/guide",
    )
    ignored = SimpleNamespace(type="char_location", title="문서", url="https://ignore.test")

    def create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="첫 문장", citations=[citation, ignored]),
                SimpleNamespace(type="web_search_tool_result"),
                SimpleNamespace(type="text", text=" 둘째 문장", citations=[duplicate]),
            ]
        )

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(anthropic_client, "_client", lambda: fake_client)

    answer, citations = anthropic_client.complete_with_web_search(
        model="claude-sonnet-5",
        system_blocks=[{"type": "text", "text": "rules"}],
        user_text="질문",
        max_tokens=500,
        max_uses=3,
    )

    assert answer == "첫 문장 둘째 문장"
    assert captured["tools"] == [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
    ]
    assert captured["messages"] == [{"role": "user", "content": "질문"}]
    assert citations == [
        {
            "kind": "web",
            "title": "공식 안내",
            "url": "https://example.test/guide",
        }
    ]
