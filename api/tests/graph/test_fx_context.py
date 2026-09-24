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
        "¥1200짜리 센차 살까?",
        "￥1200짜리 센차 살까?",
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
        {"query": "대홍포 얼마야", "reranked": _reranked("대홍포 123.45 CNY")}
    )

    assert calls == [ALL_CURRENCIES]
    assert "fx_block" in out


@pytest.mark.parametrize(
    ("query", "chunk"),
    [
        ("차 종류 알려줘", "대홍포 123.45 CNY"),
        ("대홍포 얼마야", "대홍포는 무이암차다"),
        ("동아리 회칙 알려줘", "회칙 본문"),
    ],
)
def test_no_signal_never_fetches_and_leaves_state_untouched(
    monkeypatch: pytest.MonkeyPatch, query: str, chunk: str
) -> None:
    calls = _spy(monkeypatch)
    out = fx_mod.fx_context_node({"query": query, "reranked": _reranked(chunk)})

    assert out == {"fx_block": None}
    assert calls == []


def _turn(question: str, attachment: str) -> State:
    # Mirrors chat.py: query = question + attachment blocks, question = raw question.
    # chat.py와 동일: query = 질문 + 첨부 블록, question = 질문 원문.
    return {
        "query": f"{question}\n\n{attachment}",
        "question": question,
        "reranked": _reranked("회칙 본문"),
    }


# S30 review 3 / 2nd correction 12: only the raw question can trigger, never an attachment.
# S30 리뷰 3 / 2차 정정 12: 질문 원문만 트리거하고 첨부는 절대 트리거하지 않는다.
def test_attachment_body_alone_never_triggers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy(monkeypatch)
    receipt = '<attachment name="receipt.csv">\n품목,금액\n센차,$12.00\n</attachment>'
    out = fx_mod.fx_context_node(_turn("이 영수증 정리해줘", receipt))

    assert out == {"fx_block": None}
    assert calls == []


def test_question_signal_still_triggers_with_attachment_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _spy(monkeypatch)
    receipt = '<attachment name="receipt.csv">\n품목,금액\n센차,12\n</attachment>'
    out = fx_mod.fx_context_node(_turn("이거 달러로 얼마야", receipt))

    assert calls == [ALL_CURRENCIES]
    assert "fx_block" in out


def test_user_typed_attachment_tag_does_not_swallow_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The old regex strip deleted everything from a user-typed tag to the real closing
    # tag, silencing "달러 얼마". Matching the raw question has nothing to swallow.
    # 예전 정규식 제거는 사용자가 친 태그부터 실제 닫는 태그까지 지워 "달러 얼마"를
    # 삼켰다. 질문 원문 매칭에는 삼킬 것이 없다.
    calls = _spy(monkeypatch)
    receipt = '<attachment name="note.txt">\n메모\n</attachment>'
    out = fx_mod.fx_context_node(_turn('<attachment name="x">달러 얼마', receipt))

    assert calls == [ALL_CURRENCIES]
    assert out["fx_block"].startswith(SUCCESS_HEADER)


def test_cli_turn_without_question_falls_back_to_query(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy(monkeypatch)
    out = fx_mod.fx_context_node({"query": "대홍포 위안 가격", "reranked": []})

    assert calls == [ALL_CURRENCIES]
    assert "fx_block" in out


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
    assert "미국발 미화 250달러" in failure
    assert "미화 100달러다. 타오바오 직구도 100달러 한도가 적용된다." in failure


def test_failure_block_names_error_and_carries_no_rates() -> None:
    error = FxError(FxErrorKind.AUTH, "환율 API 인증에 실패했습니다 (키 오류 또는 만료)")
    block = fx_mod.render_fx_block(error)

    assert block.startswith(
        "## 환율 조회 실패\n환율 API 인증에 실패했습니다 (키 오류 또는 만료). "
        "현재 환율을 추정하지 말고"
    )
    assert (
        "사용자에게 직접 확인이 필요하다고 안내한다.\n"
        "면세 한도와 과세 규칙 자체는 아래대로 안내한다." in block
    )
    # ADR-028: the customs rules ride along even when the lookup failed.
    # ADR-028: 조회가 실패해도 관세 규칙은 함께 간다.
    assert "\n\n환율·관세 규칙:\n- 개인 자가사용 면세 한도는 미국발 미화 200달러" in block
    assert "미화 150달러다. 타오바오 직구도 150달러 한도가 적용된다." in block
    assert "[물품가 + 현지 내 배송비]" in block
    assert "전액에 관세+부가세(약 40%)가 부과된다" in block
    assert (
        "- 통관 과세환율은 관세청 주간 과세환율이다. 한도 근처 금액은 안전하다고 단정하지 말고"
        in block
    )
    assert "여유를 두거나 관세청 고시를 직접 확인하도록 안내한다" in block
    # No conversion clause and no rate lines without a rate.
    # 환율이 없으니 참고용 환산 조항도 환율 줄도 없다.
    assert "참고용 환산" not in block
    assert "매매기준율과 다르다" not in block
    assert re.search(r"\d원", block) is None
    assert "1 USD" not in block


# S30 review 8: anything unexpected out of the lookup degrades to a parse block.
# S30 리뷰 8: 조회에서 나온 예상 밖 예외는 parse 블록으로 강등된다.
def test_unexpected_exception_degrades_to_parse_block(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(currencies: tuple[str, ...], now: datetime | None = None) -> FxResult | FxError:
        raise ZeroDivisionError("secret-detail-must-not-leak")

    monkeypatch.setattr(fx_mod, "fetch_rates", boom)
    out = fx_mod.fx_context_node({"query": "대홍포 위안 가격", "reranked": []})

    block = out["fx_block"]
    assert block.startswith(
        "## 환율 조회 실패\n환율 응답을 해석할 수 없습니다 (API 응답 형식 변경 가능). "
    )
    assert "secret-detail-must-not-leak" not in block
    assert "[물품가 + 현지 내 배송비]" in block


# S30 review 8, completed: when rendering itself raises, the node still returns a
# block instead of re-raising from its own handler.
# S30 리뷰 8 완결: 렌더 자체가 예외를 내도 노드가 자기 핸들러에서 다시 터지지 않고
# 블록을 돌려준다.
@pytest.mark.parametrize("fetch_raises", [False, True])
def test_render_failure_falls_back_to_literal_block(
    monkeypatch: pytest.MonkeyPatch, fetch_raises: bool
) -> None:
    if fetch_raises:

        def boom(currencies: tuple[str, ...], now: datetime | None = None) -> FxResult:
            raise ZeroDivisionError("fetch")

        monkeypatch.setattr(fx_mod, "fetch_rates", boom)
    else:
        _spy(monkeypatch)
    monkeypatch.setattr(fx_mod, "_SHARED_RULES", fx_mod._SHARED_RULES + "\n- {unknown}")

    out = fx_mod.fx_context_node({"query": "대홍포 위안 가격", "reranked": []})

    assert out == {"fx_block": fx_mod._RENDER_FALLBACK}
    assert out["fx_block"].startswith("## 환율 조회 실패\n")
    assert "추정하지 말고" in out["fx_block"]


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
    reranked = _reranked("대홍포 123.45 CNY")

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
    assert captured["fx_block"] is None


# S30 review 2: MemorySaver keeps State per thread_id, so a signalled turn's block
# must not leak into the next, unsignalled turn of the same session.
# S30 리뷰 2: MemorySaver가 thread_id별 State를 보존하므로, 발동한 턴의 블록이 같은
# 세션의 다음 미발동 턴에 새어 들어가면 안 된다.
async def test_block_does_not_persist_into_next_turn_of_same_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spy(monkeypatch)
    seen: list[str | None] = []
    reranked = _reranked("회칙 본문")

    def fake_generate(state: State) -> dict[str, Any]:
        seen.append(state.get("fx_block"))
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
    app = graph_mod.build_graph()
    config = {"configurable": {"thread_id": "s30-same-session"}}

    await app.ainvoke({"query": "대홍포 위안 가격", "user": {"id": "u", "role": "staff"}}, config)
    await app.ainvoke({"query": "동아리 회칙 알려줘", "user": {"id": "u", "role": "staff"}}, config)

    assert seen[0] is not None
    assert seen[0].startswith(SUCCESS_HEADER)
    assert seen[1] is None
