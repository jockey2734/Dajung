"""Serial ask helpers — pure logic, no models or services.

직렬 ask 헬퍼 — 순수 로직, 모델·서비스 불필요.
"""

from __future__ import annotations

from typing import Any

from api.app.core.config import Settings
from api.app.rag.answer import (
    build_context,
    citations_for,
    pick_model,
    pick_route,
    render,
)

_settings = Settings(_env_file=None)  # type: ignore[call-arg]


def test_route_forced_wins() -> None:
    assert pick_route("아무 질문", "handover") == "handover"
    assert pick_route("인수인계 어떻게 해?", "knowledge") == "knowledge"


def test_route_keyword_shortcut() -> None:
    assert pick_route("신임 회장이 처음 맡으면 뭐부터?", "auto") == "handover"
    assert pick_route("개완으로 우리는 법 알려줘", "auto") == "knowledge"


def test_model_split() -> None:
    assert pick_model("handover", "짧음", 1) == _settings.model_sonnet
    long_q = "이번 학기 예산과 지난 학기 비교해서 다과 지출 추이가 어땠는지 알려줘 자세히" * 2
    assert pick_model("knowledge", long_q, 5) == _settings.model_sonnet
    assert pick_model("knowledge", "짧은 질문", 5) == _settings.model_haiku
    assert pick_model("knowledge", long_q, 2) == _settings.model_haiku


def _reranked() -> list[dict[str, Any]]:
    return [
        {
            "payload": {
                "context_header": f"[문서: f{i}.md]",
                "text": f"본문 {i}",
                "source_file": f"f{i}.md",
                "locator": f"p.{i}",
                "category": "인수인계",
                "semester": "2025-1",
            },
            "rerank_score": 0.9 - i * 0.1,
        }
        for i in range(3)
    ]


def test_build_context_numbering() -> None:
    ctx = build_context(_reranked())
    assert "[1] [문서: f0.md]" in ctx and "[3] [문서: f2.md]" in ctx


def test_citations_order_and_bounds() -> None:
    answer = "먼저 회칙을 확인한다 [2]. 그다음 명단 인계 [1]. 근거 없음 [9]. 반복 [2]."
    cites = citations_for(answer, _reranked())
    assert [c["marker"] for c in cites] == [2, 1]
    assert all(c["kind"] == "doc" for c in cites)
    assert cites[0]["source_file"] == "f1.md"


def test_citations_empty_when_no_marker() -> None:
    assert citations_for("마커 없는 답", _reranked()) == []


def test_render_footer() -> None:
    cites = citations_for("답 [1].", _reranked())
    text = render("답 [1].", "handover", cites)
    assert "―― 출처 ――" in text
    assert "[1] f0.md · 인수인계 · 2025-1 · p.0" in text
    assert "(route: handover)" in text


def test_render_no_citations() -> None:
    text = render("자료 없음 답변", "knowledge", [])
    assert "출처" not in text
    assert "(route: knowledge)" in text
