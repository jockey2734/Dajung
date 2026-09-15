"""Conditional exchange-rate context node (ADR-028, webapp-spec S30-2/S30-3).

조건부 환율 컨텍스트 노드 (ADR-028, webapp-spec S30-2/S30-3).
Deterministic regex trigger between rerank and generate — no model judgment.
rerank와 generate 사이의 결정적 정규식 트리거 — 모델 판단 없음.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from api.app.core.config import settings
from api.app.core.fx import DEFAULT_CURRENCIES, FxError, FxResult, fetch_rates, unexpected_error
from api.app.graph.state import State

# Both yen signs: U+00A5 (keyboards, Taobao, Japanese pages) and U+FFE5 fullwidth.
# 엔 기호 둘 다: U+00A5(키보드·타오바오·일본 페이지)와 U+FFE5 전각.
_CURRENCY = re.compile(r"위안|元|CNY|CNH|¥|￥|달러|USD|\$|유로|EUR|€|파운드|GBP|£|엔화|JPY")
_INTENT = re.compile(r"직구|타오바오|해외\s?배송|배대지|면세|관세|공동\s?구매|공구|환율|환산")
_PRICE = re.compile(r"가격|얼마|비용|예산|구매|살까|주문")
# chat.py appends `<attachment name="…">…</attachment>` blocks to state["query"]; the
# trigger must see the question only, or a receipt's "$12.00" alone fires a lookup
# (S30 review 3). Bodies are html-escaped, so the closing tag cannot occur inside one.
# chat.py는 state["query"]에 `<attachment name="…">…</attachment>` 블록을 붙인다.
# 트리거는 질문만 봐야 한다 — 아니면 영수증의 "$12.00"만으로 조회가 발동한다 (S30
# 리뷰 3). 본문은 html-escape돼 있어 닫는 태그가 안에 나올 수 없다.
_ATTACHMENT_BLOCK = re.compile(r"<attachment\b[^>]*>.*?</attachment>", re.DOTALL)

_RULES_HEADER = "환율·관세 규칙:"
# Success only — there is no rate to convert with in the failure block.
# 성공 전용 — 실패 블록에는 환산할 환율이 없다.
_CONVERSION_RULE = (
    "- 위 환율은 참고용 환산이다. 실제 결제액은 카드사 환율·수수료·지불수속비로 달라진다.\n"
    "  과거 구매 기록의 원화 총액이 있으면 그 실결제액을 우선 기준으로 삼는다."
)
# Shared by success and failure (ADR-028: the customs rules must always be injected).
# 성공·실패 공통 (ADR-028: 관세 규칙은 항상 주입한다).
_SHARED_RULES = (
    "- 개인 자가사용 면세 한도는 미국발 미화 {us}달러, 그 외 모든 국가(중국·유럽·영국·일본 포함)\n"
    "  미화 {other}달러다. 타오바오 직구도 {other}달러 한도가 적용된다.\n"
    "- 한도 판단 기준액은 [물품가 + 현지 내 배송비] 합계다. 1센트라도 초과하면 초과분이 아니라\n"
    "  전액에 관세+부가세(약 40%)가 부과된다."
)
# Final clause is the ADR-028 honesty boundary — never delete or soften it.
# 마지막 조항은 ADR-028 정직성 경계 — 삭제·완화 금지.
_SUCCESS_CUSTOMS_RULE = (
    "- 통관 과세환율은 관세청 주간 과세환율이며 위 매매기준율과 다르다. 한도 근처 금액은\n"
    "  안전하다고 단정하지 말고 여유를 두거나 관세청 고시를 직접 확인하도록 안내한다."
)
_FAILURE_CUSTOMS_RULE = (
    "- 통관 과세환율은 관세청 주간 과세환율이다. 한도 근처 금액은 안전하다고 단정하지 말고\n"
    "  여유를 두거나 관세청 고시를 직접 확인하도록 안내한다."
)
_FAILURE_LEAD = (
    "## 환율 조회 실패\n"
    "{detail}. 현재 환율을 추정하지 말고, 사용자에게 직접 확인이 필요하다고 안내한다.\n"
    "면세 한도와 과세 규칙 자체는 아래대로 안내한다."
)


def should_fetch_fx(query: str, reranked: list[dict[str, Any]]) -> bool:
    """Trigger: currency/intent word in the question, or price word + currency in a chunk.

    발동: 질문에 통화·의도어, 또는 질문에 가격어 + 청크 본문에 통화어.
    """
    if _CURRENCY.search(query) or _INTENT.search(query):
        return True
    if not _PRICE.search(query):
        return False
    # Guards against a generic question that merely happened to retrieve a buying guide.
    # 구매 가이드가 우연히 검색된 일반 질문에 불필요한 외부 호출을 막는다.
    return any(
        _CURRENCY.search(str(candidate.get("payload", {}).get("text", "")))
        for candidate in reranked
    )


def _format_rate(rate: Decimal) -> str:
    return f"{rate.quantize(Decimal('0.01')):,}"


def _rules(bullets: list[str]) -> str:
    return "\n".join([_RULES_HEADER, *bullets]).format(
        us=settings.fx_de_minimis_usd_us, other=settings.fx_de_minimis_usd
    )


def render_fx_block(outcome: FxResult | FxError) -> str:
    """Render the finished prompt block for success or for a named failure.

    성공 또는 종류가 밝혀진 실패에 대한 완성 프롬프트 블록을 만든다.
    """
    if isinstance(outcome, FxError):
        lead = _FAILURE_LEAD.format(detail=outcome.detail)
        return f"{lead}\n\n{_rules([_SHARED_RULES, _FAILURE_CUSTOMS_RULE])}"
    lines = [f"## 환율 ({outcome.source}, {outcome.base_date.isoformat()} 고시 기준)"]
    lines.extend(f"- 1 {code} = {_format_rate(rate)}원" for code, rate in outcome.rates.items())
    rules = _rules([_CONVERSION_RULE, _SHARED_RULES, _SUCCESS_CUSTOMS_RULE])
    return "\n".join(lines) + "\n\n" + rules


def prepend_fx_block(text: str, fx_block: str | None) -> str:
    """Prepend the optional FX block ahead of the 자료 material (S30-5, prepend_history shape).

    선택적 환율 블록을 자료 앞에 붙인다 (S30-5, prepend_history와 같은 형태).
    """
    return f"{fx_block}\n\n{text}" if fx_block else text


def fx_context_node(state: State) -> dict[str, Any]:
    """Fetch once when signalled; otherwise clear the block and call nothing.

    신호가 있을 때만 1회 조회한다. 아니면 아무것도 호출하지 않고 블록을 비운다.
    """
    assert "query" in state
    question = _ATTACHMENT_BLOCK.sub("", state["query"])
    if not should_fetch_fx(question, state.get("reranked", [])):
        # Explicit None: the checkpointer keeps State across turns of a session, so an
        # omitted key would carry the previous turn's block into an unrelated answer
        # (S30 review 2).
        # 명시적 None: 체크포인터가 세션의 턴 간 State를 보존하므로 키를 빼먹으면
        # 직전 턴의 블록이 무관한 답변에 딸려 들어간다 (S30 리뷰 2).
        return {"fx_block": None}
    try:
        block = render_fx_block(fetch_rates(DEFAULT_CURRENCIES))
    except Exception as exc:
        # A quote-shaped surprise must not end the whole turn as an SSE error.
        # 호가 형태의 돌발 상황이 턴 전체를 SSE 오류로 끝내면 안 된다.
        block = render_fx_block(unexpected_error(exc))
    return {"fx_block": block}
