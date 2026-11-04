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


def _capture_create(
    monkeypatch: pytest.MonkeyPatch, content: list[Any] | None = None
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(content=content or [SimpleNamespace(type="text", text="답")])

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(anthropic_client, "_client", lambda: fake_client)
    return captured


def test_complete_omits_system_when_no_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    # SDK 1.x sends system=None as null, which the API rejects with a 400.
    # SDK 1.x는 system=None을 null로 보내고 API는 400으로 거부한다.
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-sonnet-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert "system" not in captured


def test_complete_passes_system_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_create(monkeypatch)
    blocks = [{"type": "text", "text": "rules"}]
    anthropic_client.complete(
        model="claude-sonnet-5", system_blocks=blocks, user_text="질문", max_tokens=50
    )
    assert captured["system"] == blocks


def test_web_search_omits_system_when_no_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_create(monkeypatch)
    anthropic_client.complete_with_web_search(
        model="claude-sonnet-5", system_blocks=[], user_text="질문", max_tokens=50, max_uses=1
    )
    assert "system" not in captured


def test_complete_reads_text_blocks_by_type(monkeypatch: pytest.MonkeyPatch) -> None:
    # A response can start with a thinking block; only text blocks form the answer.
    # 응답이 thinking 블록으로 시작할 수 있다. 답은 text 블록만으로 만든다.
    _capture_create(
        monkeypatch,
        content=[
            SimpleNamespace(type="thinking", thinking="", signature="sig"),
            SimpleNamespace(type="text", text="제목"),
        ],
    )
    out = anthropic_client.complete(
        model="claude-sonnet-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert out == "제목"
