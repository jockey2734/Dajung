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
from api.app.core.fx import DEFAULT_CURRENCIES, FxError, FxResult, fetch_rates
from api.app.graph.state import State

_CURRENCY = re.compile(r"위안|元|CNY|CNH|￥|달러|USD|\$|유로|EUR|€|파운드|GBP|£|엔화|JPY")
_INTENT = re.compile(r"직구|타오바오|해외\s?배송|배대지|면세|관세|공동\s?구매|공구|환율|환산")
_PRICE = re.compile(r"가격|얼마|비용|예산|구매|살까|주문")

# Final clause is the ADR-028 honesty boundary — never delete or soften it.
# 마지막 조항은 ADR-028 정직성 경계 — 삭제·완화 금지.
_FX_RULES = """환율·관세 규칙:
- 위 환율은 참고용 환산이다. 실제 결제액은 카드사 환율·수수료·지불수속비로 달라진다.
  과거 구매 기록의 원화 총액이 있으면 그 실결제액을 우선 기준으로 삼는다.
- 개인 자가사용 면세 한도는 미국발 미화 {us}달러, 그 외 모든 국가(중국·유럽·영국·일본 포함)
  미화 {other}달러다. 타오바오 직구도 {other}달러 한도가 적용된다.
- 한도 판단 기준액은 [물품가 + 현지 내 배송비] 합계다. 1센트라도 초과하면 초과분이 아니라
  전액에 관세+부가세(약 40%)가 부과된다.
- 통관 과세환율은 관세청 주간 과세환율이며 위 매매기준율과 다르다. 한도 근처 금액은
  안전하다고 단정하지 말고 여유를 두거나 관세청 고시를 직접 확인하도록 안내한다."""

_FAILURE = (
    "## 환율 조회 실패\n"
    "{detail}. 현재 환율을 추정하지 말고, 사용자에게 직접 확인이 필요하다고 안내한다.\n"
    "면세 한도(미국발 {us}달러 / 그 외 {other}달러)와 40% 과세 규칙 자체는 "
    "그대로 안내해도 된다."
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


def render_fx_block(outcome: FxResult | FxError) -> str:
    """Render the finished prompt block for success or for a named failure.

    성공 또는 종류가 밝혀진 실패에 대한 완성 프롬프트 블록을 만든다.
    """
    us, other = settings.fx_de_minimis_usd_us, settings.fx_de_minimis_usd
    if isinstance(outcome, FxError):
        return _FAILURE.format(detail=outcome.detail, us=us, other=other)
    lines = [f"## 환율 ({outcome.source}, {outcome.base_date.isoformat()} 고시 기준)"]
    lines.extend(f"- 1 {code} = {_format_rate(rate)}원" for code, rate in outcome.rates.items())
    return "\n".join(lines) + "\n\n" + _FX_RULES.format(us=us, other=other)


def prepend_fx_block(text: str, fx_block: str | None) -> str:
    """Prepend the optional FX block ahead of the 자료 material (S30-5, prepend_history shape).

    선택적 환율 블록을 자료 앞에 붙인다 (S30-5, prepend_history와 같은 형태).
    """
    return f"{fx_block}\n\n{text}" if fx_block else text


def fx_context_node(state: State) -> dict[str, Any]:
    """Fetch once when signalled; otherwise leave State untouched and call nothing.

    신호가 있을 때만 1회 조회한다. 아니면 아무것도 호출하지 않고 State를 바꾸지 않는다.
    """
    assert "query" in state
    if not should_fetch_fx(state["query"], state.get("reranked", [])):
        return {}
    return {"fx_block": render_fx_block(fetch_rates(DEFAULT_CURRENCIES))}
