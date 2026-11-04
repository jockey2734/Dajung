"""Anthropic web-search adapter contract with a fake SDK client.

가짜 SDK 클라이언트로 검증하는 Anthropic 웹 검색 어댑터 계약.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from api.app.core.config import settings
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
    monkeypatch: pytest.MonkeyPatch,
    content: list[Any] | None = None,
    stop_reason: str = "end_turn",
    stop_details: Any = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def response() -> Any:
        return SimpleNamespace(
            content=content or [SimpleNamespace(type="text", text="답")],
            stop_reason=stop_reason,
            stop_details=stop_details,
            model="fake",
        )

    def create(**kwargs: Any) -> Any:
        captured.update(kwargs, endpoint="messages")
        return response()

    def beta_create(**kwargs: Any) -> Any:
        captured.update(kwargs, endpoint="beta")
        return response()

    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=create),
        beta=SimpleNamespace(messages=SimpleNamespace(create=beta_create)),
    )
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


def test_haiku_calls_disable_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    # Haiku 5.5 thinks by default; Haiku calls are short (titles, headers, memory) and
    # stay thinking-free as on Haiku 4.5 so thinking cannot eat the small max_tokens.
    # Haiku 5.5는 기본으로 생각한다. Haiku 호출은 짧아(제목·헤더·메모리) 4.5처럼 생각 없이
    # 둬서 작은 max_tokens를 생각이 다 쓰지 않게 한다.
    monkeypatch.setattr(settings, "model_haiku", "claude-haiku-5-5")
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-haiku-5-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert captured["thinking"] == {"type": "disabled"}


def test_non_haiku_calls_leave_thinking_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "model_haiku", "claude-haiku-5-5")
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-sonnet-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert "thinking" not in captured


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


def test_sonnet_calls_use_server_side_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "model_sonnet", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "anthropic_fallbacks", True)
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-sonnet-5-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert captured["endpoint"] == "beta"
    assert captured["betas"] == ["server-side-fallback-2026-07-01"]
    assert captured["fallbacks"] == "default"


def test_opus_calls_use_server_side_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "model_opus", "claude-opus-5-5")
    monkeypatch.setattr(settings, "anthropic_fallbacks", True)
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-opus-5-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert captured["endpoint"] == "beta"
    assert captured["fallbacks"] == "default"


def test_fallback_switch_off_uses_plain_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "model_sonnet", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "anthropic_fallbacks", False)
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-sonnet-5-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert captured["endpoint"] == "messages"
    assert "fallbacks" not in captured and "betas" not in captured


def test_haiku_calls_skip_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Haiku 5.5 has no server-side fallback.
    # Haiku 5.5에는 서버 측 폴백이 없다.
    monkeypatch.setattr(settings, "model_haiku", "claude-haiku-5-5")
    monkeypatch.setattr(settings, "anthropic_fallbacks", True)
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-haiku-5-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert captured["endpoint"] == "messages"


def test_effort_goes_into_output_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-sonnet-5-5",
        system_blocks=[],
        user_text="질문",
        max_tokens=50,
        effort="high",
    )
    assert captured["output_config"] == {"effort": "high"}


def test_no_effort_sends_no_output_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_create(monkeypatch)
    anthropic_client.complete(
        model="claude-sonnet-5-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert "output_config" not in captured


def test_web_search_passes_effort_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "model_sonnet", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "anthropic_fallbacks", True)
    captured = _capture_create(monkeypatch)
    anthropic_client.complete_with_web_search(
        model="claude-sonnet-5-5",
        system_blocks=[],
        user_text="질문",
        max_tokens=50,
        max_uses=1,
        effort="low",
    )
    assert captured["endpoint"] == "beta"
    assert captured["output_config"] == {"effort": "low"}
    assert captured["tools"][0]["name"] == "web_search"


def test_refusal_raises_with_category(monkeypatch: pytest.MonkeyPatch) -> None:
    # A refusal is HTTP 200 with stop_reason "refusal"; content is empty or partial.
    # 거절은 HTTP 200 + stop_reason "refusal"이며 content는 비었거나 일부다.
    _capture_create(
        monkeypatch,
        content=[SimpleNamespace(type="text", text="일부")],
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="general_harms"),
    )
    with pytest.raises(anthropic_client.ModelRefusalError) as caught:
        anthropic_client.complete(
            model="claude-sonnet-5-5", system_blocks=[], user_text="질문", max_tokens=50
        )
    assert caught.value.category == "general_harms"


def test_refusal_without_details_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_create(monkeypatch, content=[], stop_reason="refusal", stop_details=None)
    with pytest.raises(anthropic_client.ModelRefusalError) as caught:
        anthropic_client.complete_with_web_search(
            model="claude-sonnet-5-5",
            system_blocks=[],
            user_text="질문",
            max_tokens=50,
            max_uses=1,
        )
    assert caught.value.category is None


def test_fallback_switch_block_is_not_answer_text(monkeypatch: pytest.MonkeyPatch) -> None:
    # A served fallback adds a "fallback" block before the rescuing model's text.
    # 폴백이 동작하면 구조 모델의 텍스트 앞에 "fallback" 블록이 붙는다.
    _capture_create(
        monkeypatch,
        content=[SimpleNamespace(type="fallback"), SimpleNamespace(type="text", text="답변")],
    )
    out = anthropic_client.complete(
        model="claude-sonnet-5-5", system_blocks=[], user_text="질문", max_tokens=50
    )
    assert out == "답변"
