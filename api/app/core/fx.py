"""Exchange-rate lookup — 한국수출입은행 매매기준율 (ADR-028, webapp-spec S30-1).

환율 조회 — 한국수출입은행 매매기준율 (ADR-028, webapp-spec S30-1).
Lives in core/ so graph nodes import it without SQLAlchemy (same as clock.py).
그래프 노드가 SQLAlchemy 없이 import하도록 core/에 둔다 (clock.py와 동일).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

import httpx

from api.app.core.account_term import to_utc
from api.app.core.clock import KST, now_kst
from api.app.core.config import settings
from api.app.core.logging import get_logger

log = get_logger(__name__)


def _silence_httpx_request_log() -> None:
    # httpx logs 'HTTP Request: GET <full URL>' at INFO on the stdlib `httpx` logger,
    # and that URL carries authkey. Pin it to WARNING at import and again per fetch —
    # the Anthropic SDK's ANTHROPIC_LOG=info raises the same logger to INFO later.
    # httpx는 stdlib `httpx` 로거에 INFO로 'HTTP Request: GET <전체 URL>'을 남기고 그
    # URL에는 authkey가 실린다. import 시점과 조회 때마다 WARNING으로 고정한다 —
    # Anthropic SDK의 ANTHROPIC_LOG=info가 나중에 같은 로거를 INFO로 올린다.
    logging.getLogger("httpx").setLevel(logging.WARNING)


_silence_httpx_request_log()

# oapi host only — www.koreaexim.go.kr was retired 2026-04-30 and no longer answers.
# oapi 호스트만 — www.koreaexim.go.kr은 2026-04-30 종료돼 더 이상 응답하지 않는다.
FX_ENDPOINT = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
SOURCE_NAME = "한국수출입은행 매매기준율"
# Taobao (CNY) · US de minimis (USD) · Mariage Frères (EUR) · Fortnum (GBP) · Japanese tea (JPY).
# 타오바오(CNY) · 미국 면세한도(USD) · 마리아쥬 프레르(EUR) · 포트넘(GBP) · 일본차(JPY).
DEFAULT_CURRENCIES: tuple[str, ...] = ("CNY", "USD", "EUR", "GBP", "JPY")

# The API quotes yuan as offshore CNH; documents and users say CNY.
# API는 위안화를 역외 CNH로 호가하고, 문서와 사용자는 CNY라 부른다.
_UNIT_ALIASES = {"CNY": "CNH"}
# `JPY(100)`-style units quote per 100 (also IDR/VND/KHR). The suffix is parsed
# generically — no per-currency hardcoding, so adding a currency can't reintroduce it.
# `JPY(100)` 형태는 100단위 호가(IDR/VND/KHR도 동일). 접미를 범용 파싱한다 —
# 통화별 하드코딩이 없어 통화를 추가해도 같은 함정이 재발하지 않는다.
_UNIT_RE = re.compile(r"^([A-Z]{3})(?:\((\d+)\))?$")
_RESULT_OK = 1
_SEARCHDATE_FMT = "%Y%m%d"


class FxErrorKind(StrEnum):
    NO_KEY = "no_key"
    AUTH = "auth"
    QUOTA = "quota"
    DATA = "data"
    NO_DATA = "no_data"
    TIMEOUT = "timeout"
    HTTP = "http"
    NETWORK = "network"
    PARSE = "parse"
    MISSING_CURRENCY = "missing_currency"


# API `result` codes other than 1 (webapp-spec S30-1 table).
# 1이 아닌 API `result` 코드 (webapp-spec S30-1 표).
_RESULT_ERRORS = {2: FxErrorKind.DATA, 3: FxErrorKind.AUTH, 4: FxErrorKind.QUOTA}

# User-facing sentences (webapp-spec S30-3). Placeholders only — never the key.
# 사용자 노출 문구 (webapp-spec S30-3). 자리표시자만 — 키는 절대 넣지 않는다.
_MESSAGES: dict[FxErrorKind, str] = {
    FxErrorKind.NO_KEY: "환율 API 키가 설정되지 않았습니다 (`DAJUNG_KOREAEXIM_API_KEY` 미설정)",
    FxErrorKind.AUTH: "환율 API 인증에 실패했습니다 (키 오류 또는 만료)",
    FxErrorKind.QUOTA: "환율 API 일일 요청 한도(1,000회)를 초과했습니다",
    FxErrorKind.DATA: "환율 API가 요청 형식 오류를 반환했습니다",
    FxErrorKind.NO_DATA: (
        "최근 {n}영업일 내 고시 환율을 찾지 못했습니다 (주말·공휴일 또는 고시 시각 이전)"
    ),
    FxErrorKind.TIMEOUT: "환율 조회가 {n}초 안에 응답하지 않았습니다",
    FxErrorKind.HTTP: "환율 API가 HTTP {status}를 반환했습니다",
    FxErrorKind.NETWORK: "환율 API에 연결할 수 없습니다",
    FxErrorKind.PARSE: "환율 응답을 해석할 수 없습니다 (API 응답 형식 변경 가능)",
    FxErrorKind.MISSING_CURRENCY: "응답에 {currency} 환율이 없습니다",
}


@dataclass(frozen=True)
class FxResult:
    rates: dict[str, Decimal]
    base_date: date
    source: str


@dataclass(frozen=True)
class FxError:
    kind: FxErrorKind
    # Ready-to-show Korean sentence from _MESSAGES — no key, no raw exception text.
    # _MESSAGES에서 만든 바로 노출 가능한 한국어 문구 — 키도, 예외 원문도 없다.
    detail: str


# Keyed by the requested searchdate and holding the full quoted table, so any
# currency subset is served from one fetch. functools.lru_cache has no TTL — unfit.
# 요청한 searchdate가 키이고 고시 전체 표를 담아, 어떤 통화 부분집합도 한 번의
# 조회로 서빙한다. functools.lru_cache는 TTL이 없어 부적합.
_cache: dict[str, tuple[float, FxResult]] = {}


def _fail(kind: FxErrorKind, **params: object) -> FxError:
    # parse is the early warning for an upstream format change — warn, not info.
    # parse는 API 형식 변경의 조기 경보 — info가 아니라 warning.
    if kind is FxErrorKind.PARSE:
        log.warning("fx_error", kind=str(kind))
    else:
        log.info("fx_error", kind=str(kind))
    return FxError(kind=kind, detail=_MESSAGES[kind].format(**params))


def _make_client() -> httpx.Client:
    # TLS verification stays on (ADR-028): verify=False is forbidden.
    # TLS 검증은 켠 채로 둔다 (ADR-028): verify=False 금지.
    return httpx.Client(timeout=settings.fx_timeout_s)


def _parse_table(payload: Any, searchdate: str) -> dict[str, Decimal] | None | FxError:
    """Turn one day's JSON into {cur_unit base: rate}; None when the day has no quote.

    하루치 JSON을 {cur_unit 기본코드: 환율}로 바꾼다. 그 날 고시가 없으면 None.
    """
    # The API answers null / {} / [] on non-business days and before posting time —
    # all mean "no quote for that day", never a format error (S30 review 5).
    # API는 비영업일·고시 전 시각에 null / {} / []를 돌려준다 — 전부 "그 날 고시 없음"이지
    # 형식 오류가 아니다 (S30 리뷰 5).
    if payload is None or payload == "" or payload == {} or payload == []:
        log.info("fx_no_quote", searchdate=searchdate)
        return None
    items = payload if isinstance(payload, list) else [payload]
    rates: dict[str, Decimal] = {}
    for item in items:
        if not isinstance(item, dict):
            return _fail(FxErrorKind.PARSE)
        raw_result = item.get("result")
        if raw_result is None:
            return _fail(FxErrorKind.PARSE)
        try:
            result = int(raw_result)
        except (TypeError, ValueError):
            return _fail(FxErrorKind.PARSE)
        if result != _RESULT_OK:
            log.info("fx_result", searchdate=searchdate, result=result)
            kind = _RESULT_ERRORS.get(result)
            return _fail(kind) if kind else _fail(FxErrorKind.PARSE)
        unit = _UNIT_RE.match(str(item.get("cur_unit", "")))
        if unit is None:
            return _fail(FxErrorKind.PARSE)
        try:
            rate = Decimal(str(item.get("deal_bas_r", "")).replace(",", ""))
        except InvalidOperation:
            return _fail(FxErrorKind.PARSE)
        per = unit.group(2)
        # Infinity / NaN quotes and a "(0)" unit are format errors, not values —
        # they would otherwise raise out of quantize / division (S30 review 8).
        # Infinity / NaN 호가와 "(0)" 단위는 값이 아니라 형식 오류다 — 그대로 두면
        # quantize / 나눗셈에서 예외가 난다 (S30 리뷰 8).
        if not rate.is_finite() or (per is not None and Decimal(per) == 0):
            return _fail(FxErrorKind.PARSE)
        rates[unit.group(1)] = rate / Decimal(per) if per else rate
    log.info("fx_quote", searchdate=searchdate, result=_RESULT_OK, currencies=len(rates))
    return rates


def _request_day(client: httpx.Client, day: date) -> dict[str, Decimal] | None | FxError:
    searchdate = day.strftime(_SEARCHDATE_FMT)
    params = {"authkey": settings.koreaexim_api_key, "searchdate": searchdate, "data": "AP01"}
    try:
        response = client.get(FX_ENDPOINT, params=params)
    except httpx.TimeoutException:
        return _fail(FxErrorKind.TIMEOUT, n=f"{settings.fx_timeout_s:g}")
    except httpx.HTTPError:
        # Never str() the exception — httpx messages can embed the full request URL.
        # 예외를 str()하지 않는다 — httpx 메시지에 요청 URL 전체가 들어갈 수 있다.
        return _fail(FxErrorKind.NETWORK)
    if response.status_code != httpx.codes.OK:
        return _fail(FxErrorKind.HTTP, status=response.status_code)
    if not response.text.strip():
        return _parse_table("", searchdate)
    try:
        payload = response.json()
    except ValueError:
        return _fail(FxErrorKind.PARSE)
    return _parse_table(payload, searchdate)


def _fetch_table(start: date) -> FxResult | FxError:
    # Cutoff is unverified against the live API (no key at implementation time): the
    # posting hour on a business day is unknown, so an empty day just means "walk back".
    # 컷오프는 실 API로 미실측(구현 시점에 키 없음): 영업일 고시 시각을 모르므로
    # 빈 날은 "하루 역행"으로만 다룬다.
    # fx_lookback_days counts weekday attempts, not calendar days. Holiday weekdays still
    # cost an attempt: after 추석 2025 (last quote 10-02) a Monday lookup needs 8 and a
    # Tuesday 9 — hence the default of 10 (S30 review 6, 2nd correction 11).
    # fx_lookback_days는 달력일이 아니라 평일 시도 횟수다. 공휴일 평일도 1회를 쓴다:
    # 추석 2025(마지막 고시 10-02) 뒤 월요일 조회는 8회, 화요일은 9회가 필요해 기본값이
    # 10이다 (S30 리뷰 6, 2차 정정 11).
    # Re-pin here, not in the client factory — it must hold whatever builds the client.
    # 클라이언트 팩토리가 아니라 여기서 다시 고정한다 — 클라이언트를 누가 만들든 유지돼야 한다.
    _silence_httpx_request_log()
    with _make_client() as client:
        day = start
        attempts = 0
        while attempts < settings.fx_lookback_days:
            # Quotes never post on weekends — skip without counting or spending quota.
            # 주말엔 고시가 없다 — 횟수도 한도도 쓰지 않고 건너뛴다.
            if day.weekday() < 5:
                attempts += 1
                outcome = _request_day(client, day)
                if isinstance(outcome, FxError):
                    return outcome
                if outcome is not None:
                    return FxResult(rates=outcome, base_date=day, source=SOURCE_NAME)
            day -= timedelta(days=1)
    return _fail(FxErrorKind.NO_DATA, n=settings.fx_lookback_days)


def _select(table: FxResult, currencies: tuple[str, ...]) -> FxResult | FxError:
    rates: dict[str, Decimal] = {}
    for code in currencies:
        unit = _UNIT_ALIASES.get(code, code)
        if unit not in table.rates:
            return _fail(FxErrorKind.MISSING_CURRENCY, currency=code)
        rates[code] = table.rates[unit]
    return FxResult(rates=rates, base_date=table.base_date, source=table.source)


def unexpected_error(exc: BaseException) -> FxError:
    """Demote any unexpected exception to a parse failure — type name only, never str(exc).

    예상 밖 예외를 parse 실패로 강등한다 — 타입명만 남기고 str(exc)는 쓰지 않는다.
    """
    log.warning("fx_unexpected", exc_type=type(exc).__name__)
    return FxError(kind=FxErrorKind.PARSE, detail=_MESSAGES[FxErrorKind.PARSE])


def fetch_rates(currencies: tuple[str, ...], now: datetime | None = None) -> FxResult | FxError:
    """Return deal_bas_r per unit of each currency from the latest posted business day.

    최근 고시 영업일 기준 통화별 1단위 매매기준율을 반환한다.
    """
    if not settings.koreaexim_api_key:
        return _fail(FxErrorKind.NO_KEY)
    local = now_kst() if now is None else to_utc(now).astimezone(KST)
    key = local.strftime(_SEARCHDATE_FMT)
    cached = _cache.get(key)
    if cached is not None and time.monotonic() - cached[0] < settings.fx_cache_ttl_s:
        return _select(cached[1], currencies)
    table = _fetch_table(local.date())
    if isinstance(table, FxError):
        return table
    _cache[key] = (time.monotonic(), table)
    return _select(table, currencies)
