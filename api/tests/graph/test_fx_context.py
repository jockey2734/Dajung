"""fx_context node: regex trigger, prompt block text, and graph pass-through.

fx_context 노드: 정규식 트리거·프롬프트 블록 문안·그래프 통과.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from api.app.core.config import settings
from api.app.core.fx import FxError, FxErrorKind, FxResult
from api.app.graph import graph as graph_mod
from api.app.graph.nodes import fx_context as fx_mod
from api.app.graph.state import Route, State

ALL_CURRENCIES = ("CNY", "USD", "EUR", "GBP", "JPY")
SUCCESS_HEADER = "## 환율 (한국수출입은행 매매기준율, 2026-07-24 고시 기준)"


def _result() -> FxResult:
    return FxResult(
        rates={
            "CNY": Decimal("191.24"),
            "USD": Decimal("1385.5"),
            "EUR": Decimal("1502.3"),
            "GBP": Decimal("1771.8"),
            "JPY": Decimal("8.9412"),
        },
        base_date=date(2026, 7, 24),
        source="한국수출입은행 매매기준율",
    )


def _reranked(text: str) -> list[dict[str, Any]]:
    return [
        {
            "payload": {
                "context_header": "[문서: guide.md]",
                "text": text,
                "source_file": "guide.md",
                "locator": "§4",
                "category": "테스트",
                "semester": "2025-2",
            },
            "rerank_score": 0.9,
        }
    ]


def _spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def fake_fetch(currencies: tuple[str, ...], now: datetime | None = None) -> FxResult | FxError:
        calls.append(currencies)
        return _result()

    monkeypatch.setattr(fx_mod, "fetch_rates", fake_fetch)
    return calls


@pytest.mark.parametrize(
    "query",
    [
        "대홍포 위안 가격 알려줘",
        "타오바오 직구하면 관세 붙어?",
        "180유로 공구 가능?",
        "$150 넘으면?",
    ],
)
def test_currency_or_intent_in_question_triggers(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    calls = _spy(monkeypatch)
    out = fx_mod.fx_context_node({"query": query, "reranked": _reranked("환율 무관 본문")})

    assert calls == [ALL_CURRENCIES]
    assert out["fx_block"].startswith("## 환율 (")


def test_price_word_plus_currency_in_chunk_triggers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy(monkeypatch)
    out = fx_mod.fx_context_node(
        {"query": "대홍포 얼마야", "reranked": _reranked("대홍포 156.92 CNY")}
    )

    assert calls == [ALL_CURRENCIES]
    assert "fx_block" in out


@pytest.mark.parametrize(
    ("query", "chunk"),
    [
        ("차 종류 알려줘", "대홍포 156.92 CNY"),
        ("대홍포 얼마야", "대홍포는 무이암차다"),
        ("동아리 회칙 알려줘", "회칙 본문"),
    ],
)
def test_no_signal_never_fetches_and_leaves_state_untouched(
    monkeypatch: pytest.MonkeyPatch, query: str, chunk: str
) -> None:
    calls = _spy(monkeypatch)
    out = fx_mod.fx_context_node({"query": query, "reranked": _reranked(chunk)})

    assert out == {}
    assert calls == []


def test_success_block_text() -> None:
    block = fx_mod.render_fx_block(_result())
    lines = block.splitlines()

    assert lines[0] == SUCCESS_HEADER
    assert lines[1:6] == [
        "- 1 CNY = 191.24원",
        "- 1 USD = 1,385.50원",
        "- 1 EUR = 1,502.30원",
        "- 1 GBP = 1,771.80원",
        "- 1 JPY = 8.94원",
    ]
    assert lines[6] == ""
    assert lines[7] == "환율·관세 규칙:"
    assert "미국발 미화 200달러" in block
    assert "미화 150달러다. 타오바오 직구도 150달러 한도가 적용된다." in block
    assert "[물품가 + 현지 내 배송비]" in block
    assert "전액에 관세+부가세(약 40%)가 부과된다" in block
    assert "통관 과세환율은 관세청 주간 과세환율이며 위 매매기준율과 다르다" in block
    assert "안전하다고 단정하지 말고 여유를 두거나 관세청 고시를 직접 확인하도록 안내한다" in block


def test_de_minimis_numbers_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "fx_de_minimis_usd", 100)
    monkeypatch.setattr(settings, "fx_de_minimis_usd_us", 250)

    success = fx_mod.render_fx_block(_result())
    failure = fx_mod.render_fx_block(FxError(FxErrorKind.NETWORK, "환율 API에 연결할 수 없습니다"))

    assert "미국발 미화 250달러" in success
    assert "미화 100달러다" in success
    assert "면세 한도(미국발 250달러 / 그 외 100달러)" in failure


def test_failure_block_names_error_and_carries_no_rates() -> None:
    error = FxError(FxErrorKind.AUTH, "환율 API 인증에 실패했습니다 (키 오류 또는 만료)")
    block = fx_mod.render_fx_block(error)

    assert block.startswith(
        "## 환율 조회 실패\n환율 API 인증에 실패했습니다 (키 오류 또는 만료). "
        "현재 환율을 추정하지 말고"
    )
    assert "사용자에게 직접 확인이 필요하다고 안내한다" in block
    assert (
        "면세 한도(미국발 200달러 / 그 외 150달러)와 40% 과세 규칙 자체는 그대로 안내해도 된다"
        in block
    )
    assert re.search(r"\d원", block) is None
    assert "1 USD" not in block


def test_prepend_fx_block_mirrors_prepend_history() -> None:
    assert fx_mod.prepend_fx_block("자료:\n본문", None) == "자료:\n본문"
    assert fx_mod.prepend_fx_block("자료:\n본문", "## 환율") == "## 환율\n\n자료:\n본문"


def test_graph_routes_generate_paths_through_fx_context_only() -> None:
    app = graph_mod.build_graph()
    edges = {(e.source, e.target) for e in app.get_graph().edges}

    assert ("rerank", "fx_context") in edges
    assert ("fx_context", "generate") in edges
    assert ("fx_context", "generate_handover") in edges
    assert ("rerank", "generate") not in edges
    assert ("rerank", "generate_handover") not in edges
    # Retry and offer_web keep bypassing fx_context.
    # 재시도·offer_web은 계속 fx_context를 우회한다.
    assert ("rerank", "offer_web") in edges
    assert ("rerank", "retrieve_knowledge") in edges
    assert ("rerank", "retrieve_handover") in edges
    assert ("offer_web", "fx_context") not in edges


@pytest.mark.parametrize(
    ("route", "retrieve_name", "generate_name", "route_after"),
    [
        (Route.KNOWLEDGE_QUERY, "retrieve_knowledge", "generate_node", "generate"),
        (Route.HANDOVER_QUERY, "retrieve_handover", "generate_handover", "generate_handover"),
    ],
)
async def test_compiled_graph_passes_route_after_through_fx_context(
    monkeypatch: pytest.MonkeyPatch,
    route: Route,
    retrieve_name: str,
    generate_name: str,
    route_after: str,
) -> None:
    calls = _spy(monkeypatch)
    captured: dict[str, Any] = {}
    reranked = _reranked("대홍포 156.92 CNY")

    def fake_generate(state: State) -> dict[str, Any]:
        captured.update(state)
        return {"answer": "답변 [1]", "model_used": "fake"}

    monkeypatch.setattr(graph_mod, "router_node", lambda s: {"route": route, "retries": 0})
    monkeypatch.setattr(graph_mod, retrieve_name, lambda s: {"candidates": reranked})
    monkeypatch.setattr(graph_mod, "permission_node", lambda s: {})
    monkeypatch.setattr(
        graph_mod, "rerank_node", lambda s: {"reranked": reranked, "route_after": route_after}
    )
    monkeypatch.setattr(graph_mod, generate_name, fake_generate)
    monkeypatch.setattr(graph_mod, "cite_node", lambda s: {"citations": []})

    out = await graph_mod.build_graph().ainvoke(
        {"query": "대홍포 얼마야", "user": {"id": "staff-1", "role": "staff"}},
        {"configurable": {"thread_id": f"s30-{route_after}"}},
    )

    assert calls == [ALL_CURRENCIES]
    assert captured["route_after"] == route_after
    assert captured["fx_block"].startswith(SUCCESS_HEADER)
    assert out["answer"] == "답변 [1]"


async def test_compiled_graph_skips_fetch_when_unsignalled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy(monkeypatch)
    captured: dict[str, Any] = {}
    reranked = _reranked("회칙 본문")

    def fake_generate(state: State) -> dict[str, Any]:
        captured.update(state)
        return {"answer": "답변 [1]", "model_used": "fake"}

    monkeypatch.setattr(
        graph_mod, "router_node", lambda s: {"route": Route.KNOWLEDGE_QUERY, "retries": 0}
    )
    monkeypatch.setattr(graph_mod, "retrieve_knowledge", lambda s: {"candidates": reranked})
    monkeypatch.setattr(graph_mod, "permission_node", lambda s: {})
    monkeypatch.setattr(
        graph_mod, "rerank_node", lambda s: {"reranked": reranked, "route_after": "generate"}
    )
    monkeypatch.setattr(graph_mod, "generate_node", fake_generate)
    monkeypatch.setattr(graph_mod, "cite_node", lambda s: {"citations": []})

    await graph_mod.build_graph().ainvoke(
        {"query": "동아리 회칙 알려줘", "user": {"id": "staff-1", "role": "staff"}},
        {"configurable": {"thread_id": "s30-unsignalled"}},
    )

    assert calls == []
    assert "fx_block" not in captured
