"""Contextual Retrieval prompts and post-processing with a fake model. Synthetic text only.

가짜 모델로 검증하는 Contextual Retrieval 프롬프트·후처리. 합성 텍스트만 사용.
"""

from __future__ import annotations

from typing import Any

import pytest

from api.app.core.config import settings
from api.app.ingest import context_header
from api.app.ingest.chunker import Chunk
from api.app.ingest.terms import parse_terms

_TERMS = parse_terms(
    {
        "unify": {"동아리방": ["동아리실", "동방"]},
        "conditional": [
            {"wrong": "사무실", "right": "동아리방", "when_source_has": ["동아리방", "동방"]}
        ],
        "protect": ["동방미인"],
        "keep": ["집행부", "동비"],
    }
)


class _FakeModel:
    """Records prompts and replies with a fixed text (or raises).

    프롬프트를 기록하고 고정 문구로 답한다(또는 예외를 낸다).
    """

    def __init__(self, reply: str = "", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
        effort: Any = None,
    ) -> str:
        self.calls.append({"model": model, "user_text": user_text, "max_tokens": max_tokens})
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> _FakeModel:
    fake = _FakeModel()
    monkeypatch.setattr(context_header, "complete", fake)
    monkeypatch.setattr(context_header, "get_terms", lambda: _TERMS)
    return fake


def _chunk(text: str) -> Chunk:
    return Chunk(text=text, chunk_index=0, total_chunks=1, locator="sec:0")


def _header(chunk_text: str, source_file: str = "행사_기획서.md", summary: str = "기획서.") -> str:
    return context_header.header_for_chunk(
        _chunk(chunk_text),
        source_file=source_file,
        category="운영/활동계획-일정",
        semester="2099-1",
        doc_summary=summary,
    )


# --- document description ---


def test_summary_prompt_asks_what_the_document_is(model: _FakeModel) -> None:
    model.reply = "행사 기획서."
    context_header.summarize_document("OT 진행 계획과 집행부 역할 분담.")
    prompt = model.calls[0]["user_text"]
    assert "어떤 문서인지 설명하세요" in prompt
    assert "사람 이름은 쓰지 말고" in prompt
    assert "원문 표기 그대로 쓰세요" in prompt
    assert "원문 표기 그대로 쓸 용어: OT, 집행부\n\n문서:\nOT 진행 계획" in prompt
    assert model.calls[0]["model"] == settings.model_haiku
    assert model.calls[0]["max_tokens"] == settings.max_tokens_header


def test_summary_prompt_has_no_term_line_when_nothing_found(model: _FakeModel) -> None:
    model.reply = "안내문."
    context_header.summarize_document("차 우리는 온도 안내.")
    prompt = model.calls[0]["user_text"]
    assert "쓸 용어:" not in prompt
    assert "쓰세요.\n\n문서:\n차 우리는 온도 안내." in prompt


def test_summary_terms_come_from_the_text_sent(model: _FakeModel) -> None:
    model.reply = "안내문."
    cut = context_header._DOC_SUMMARY_MAX_CHARS
    context_header.summarize_document("가" * cut + " OT")
    assert "쓸 용어:" not in model.calls[0]["user_text"]


def test_summary_output_is_unified(model: _FakeModel) -> None:
    model.reply = "  동아리실 사용 규칙과 동방미인 시음 공지.  "
    out = context_header.summarize_document("동방 사용 규칙. 동방미인 시음.")
    assert out == "동아리방 사용 규칙과 동방미인 시음 공지."


def test_summary_conditional_fix_checks_the_body(model: _FakeModel) -> None:
    model.reply = "사무실 이용 수칙."
    assert context_header.summarize_document("동방 퇴실 수칙.") == "동아리방 이용 수칙."
    assert context_header.summarize_document("정규활동 공지.") == "사무실 이용 수칙."


def test_summary_failure_returns_empty(model: _FakeModel) -> None:
    model.error = RuntimeError("boom")
    assert context_header.summarize_document("본문") == ""


# --- chunk header ---


def test_header_prompt_carries_description_and_role_question(model: _FakeModel) -> None:
    model.reply = "기획서 중 일정 부분."
    _header("일정표와 준비물.", summary="행사 기획서.")
    prompt = model.calls[0]["user_text"]
    assert "문서 설명: 행사 기획서." in prompt
    assert "어떤 부분이며 어떤 역할을 하는지" in prompt
    assert f"{settings.header_context_max_chars}자 이내" in prompt
    assert "사람 이름은 쓰지 말고" in prompt
    assert prompt.endswith("청크:\n일정표와 준비물.")


def test_header_terms_include_file_name(model: _FakeModel) -> None:
    model.reply = "OT 자료 중 일정 부분."
    _header("동비 납부 일정.", source_file="OT_자료.md")
    assert "원문 표기 그대로 쓸 용어: OT, 동비\n\n청크:" in model.calls[0]["user_text"]


def test_header_output_is_unified_and_wrapped(model: _FakeModel) -> None:
    model.reply = "사무실 수칙 중 퇴실 점검 부분."
    out = _header("동방 퇴실 시 전등을 끈다.")
    assert out.endswith("\n[맥락: 동아리방 수칙 중 퇴실 점검 부분.]")


def test_header_conditional_fix_checks_the_chunk(model: _FakeModel) -> None:
    model.reply = "사무실 수칙 부분."
    assert "[맥락: 사무실 수칙 부분.]" in _header("정규활동 일정.")


def test_header_is_cut_to_max_chars(model: _FakeModel, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "header_context_max_chars", 10)
    model.reply = "가" * 30
    assert _header("본문").endswith(f"[맥락: {'가' * 10}]")


def test_header_failure_keeps_base_line(model: _FakeModel) -> None:
    model.error = RuntimeError("boom")
    assert _header("본문") == "[문서: 행사_기획서.md | sec:0 | 분류: 운영/활동계획-일정]"


def test_header_skips_model_without_summary(model: _FakeModel) -> None:
    assert (
        _header("본문", summary="") == "[문서: 행사_기획서.md | sec:0 | 분류: 운영/활동계획-일정]"
    )
    assert model.calls == []
