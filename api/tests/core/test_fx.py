"""Exchange-rate client: unit parsing, lookback, error kinds, TTL cache, key hygiene.

환율 클라이언트: 단위 파싱·역행·오류 종류·TTL 캐시·키 위생.
Every HTTP exchange goes through httpx.MockTransport — nothing leaves the process.
모든 HTTP 교환은 httpx.MockTransport를 거친다 — 프로세스 밖으로 나가는 것은 없다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from api.app.core import fx
from api.app.core.clock import KST
from api.app.core.config import settings
from api.app.core.fx import DEFAULT_CURRENCIES, FxError, FxErrorKind, FxResult, fetch_rates

# Synthetic credential sentinel — asserted absent from every message and log line.
# 합성 자격증명 표식 — 모든 문구·로그 줄에 없음을 단언한다.
SENTINEL = "koreaexim-sentinel-must-not-leak"
FRIDAY = datetime(2026, 7, 24, 12, 0, tzinfo=KST)
MONDAY = datetime(2026, 7, 27, 9, 0, tzinfo=KST)

Handler = Callable[[httpx.Request], httpx.Response]


def _quote(cur_unit: str, deal_bas_r: str) -> dict[str, Any]:
    return {"result": 1, "cur_unit": cur_unit, "cur_nm": cur_unit, "deal_bas_r": deal_bas_r}


FULL_TABLE = [
    _quote("CNH", "191.24"),
    _quote("USD", "1,385.5"),
    _quote("EUR", "1,502.3"),
    _quote("GBP", "1,771.8"),
    _quote("JPY(100)", "894.12"),
]


class _Recorder:
    """Structlog stand-in that keeps every event and kwarg for leak assertions.

    누수 단언용으로 모든 이벤트와 kwarg를 보관하는 structlog 대역.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **kw: Any) -> None:
        self.calls.append((event, kw))

    def warning(self, event: str, **kw: Any) -> None:
        self.calls.append((event, kw))


@pytest.fixture
def fx_env(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    monkeypatch.setattr(settings, "koreaexim_api_key", SENTINEL)
    monkeypatch.setattr(settings, "fx_timeout_s", 5.0)
    monkeypatch.setattr(settings, "fx_lookback_days", 7)
    monkeypatch.setattr(settings, "fx_cache_ttl_s", 3600)
    monkeypatch.setattr(fx, "_cache", {})
    recorder = _Recorder()
    monkeypatch.setattr(fx, "log", recorder)
    return recorder


def _install(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(
        fx, "_make_client", lambda: httpx.Client(transport=httpx.MockTransport(wrapped))
    )
    return seen


def _by_date(tables: dict[str, list[dict[str, Any]]]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=tables.get(request.url.params["searchdate"], []))

    return handler


def _raising(exc: Exception) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


def test_maps_cny_to_cnh_parses_per_100_units_and_commas(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _install(monkeypatch, _by_date({"20260724": FULL_TABLE}))
    out = fetch_rates(DEFAULT_CURRENCIES, now=FRIDAY)

    assert isinstance(out, FxResult)
    assert out.rates["CNY"] == Decimal("191.24")
    assert out.rates["USD"] == Decimal("1385.5")
    assert out.rates["JPY"] == Decimal("8.9412")
    assert list(out.rates) == list(DEFAULT_CURRENCIES)
    assert out.base_date == date(2026, 7, 24)
    assert out.source == "한국수출입은행 매매기준율"
    assert len(seen) == 1
    params = seen[0].url.params
    assert params["searchdate"] == "20260724"
    assert params["data"] == "AP01"
    assert params["authkey"] == SENTINEL
    assert seen[0].url.scheme == "https"
    assert seen[0].url.host == "oapi.koreaexim.go.kr"


def test_empty_day_walks_back_to_previous_business_day_skipping_weekend(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _install(monkeypatch, _by_date({"20260724": FULL_TABLE}))
    out = fetch_rates(("USD",), now=MONDAY)

    assert isinstance(out, FxResult)
    assert out.base_date == date(2026, 7, 24)
    # Sun 26 / Sat 25 are skipped locally — no quota spent on them.
    # 26일(일)·25일(토)은 로컬에서 건너뛴다 — 한도를 쓰지 않는다.
    assert [r.url.params["searchdate"] for r in seen] == ["20260727", "20260724"]


def test_lookback_exhausted_reports_no_data(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "fx_lookback_days", 3)
    seen = _install(monkeypatch, _by_date({}))
    out = fetch_rates(("USD",), now=MONDAY)

    assert out == FxError(
        FxErrorKind.NO_DATA,
        "최근 3영업일 내 고시 환율을 찾지 못했습니다 (주말·공휴일 또는 고시 시각 이전)",
    )
    # Three weekday attempts spanning the weekend: Mon 27, Fri 24, Thu 23 (S30 review 6).
    # 주말을 넘는 평일 3회 시도: 27(월)·24(금)·23(목) (S30 리뷰 6).
    assert [r.url.params["searchdate"] for r in seen] == ["20260727", "20260724", "20260723"]


# S30 review 5: null / {} / "" / [] bodies mean "no quote that day" → walk back.
# S30 리뷰 5: null / {} / "" / [] 본문은 "그 날 고시 없음" → 역행.
@pytest.mark.parametrize("body", [b"null", b"{}", b"", b"   ", b"[]"])
def test_empty_shaped_bodies_walk_back_instead_of_parse_error(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["searchdate"] == "20260727":
            return httpx.Response(200, content=body, headers={"content-type": "application/json"})
        return httpx.Response(200, json=FULL_TABLE)

    seen = _install(monkeypatch, handler)
    out = fetch_rates(("USD",), now=MONDAY)

    assert isinstance(out, FxResult)
    assert out.base_date == date(2026, 7, 24)
    assert [r.url.params["searchdate"] for r in seen] == ["20260727", "20260724"]
    assert not [event for event, _kw in fx_env.calls if event == "fx_error"]


@pytest.mark.parametrize(
    ("code", "kind"),
    [(2, FxErrorKind.DATA), (3, FxErrorKind.AUTH), (4, FxErrorKind.QUOTA)],
)
def test_result_codes_map_to_error_kinds_without_walking_back(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch, code: int, kind: FxErrorKind
) -> None:
    seen = _install(monkeypatch, lambda request: httpx.Response(200, json=[{"result": code}]))
    out = fetch_rates(("USD",), now=MONDAY)

    assert isinstance(out, FxError)
    assert out.kind is kind
    assert len(seen) == 1
    if kind is FxErrorKind.AUTH:
        assert "키 오류 또는 만료" in out.detail


@pytest.mark.parametrize(
    ("handler", "kind", "fragment"),
    [
        (_raising(httpx.ReadTimeout("slow")), FxErrorKind.TIMEOUT, "5초 안에"),
        (_raising(httpx.ConnectError("down")), FxErrorKind.NETWORK, "연결할 수 없습니다"),
        (lambda request: httpx.Response(500, text="boom"), FxErrorKind.HTTP, "HTTP 500"),
        (lambda request: httpx.Response(200, content=b"not json"), FxErrorKind.PARSE, "해석"),
        (
            lambda request: httpx.Response(200, json=[_quote("USD", "n/a")]),
            FxErrorKind.PARSE,
            "형식 변경 가능",
        ),
        (
            lambda request: httpx.Response(200, json=[{"result": 1, "cur_unit": "usd?"}]),
            FxErrorKind.PARSE,
            "해석",
        ),
        (
            lambda request: httpx.Response(200, json=[_quote("USD(0)", "1")]),
            FxErrorKind.PARSE,
            "해석",
        ),
        (
            lambda request: httpx.Response(200, json=[_quote("USD", "Infinity")]),
            FxErrorKind.PARSE,
            "해석",
        ),
        (
            lambda request: httpx.Response(200, json=[_quote("USD", "sNaN")]),
            FxErrorKind.PARSE,
            "해석",
        ),
        (
            lambda request: httpx.Response(200, json=[_quote("USD", "NaN")]),
            FxErrorKind.PARSE,
            "해석",
        ),
    ],
)
def test_transport_and_payload_failures_name_their_kind(
    fx_env: _Recorder,
    monkeypatch: pytest.MonkeyPatch,
    handler: Handler,
    kind: FxErrorKind,
    fragment: str,
) -> None:
    _install(monkeypatch, handler)
    out = fetch_rates(("USD",), now=FRIDAY)

    assert isinstance(out, FxError)
    assert out.kind is kind
    assert fragment in out.detail


def test_missing_key_short_circuits_without_http(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "koreaexim_api_key", "")
    seen = _install(monkeypatch, _by_date({"20260724": FULL_TABLE}))
    out = fetch_rates(("USD",), now=FRIDAY)

    assert isinstance(out, FxError)
    assert out.kind is FxErrorKind.NO_KEY
    assert "DAJUNG_KOREAEXIM_API_KEY" in out.detail
    assert seen == []


def test_missing_currency_in_quote_table(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, _by_date({"20260724": [_quote("USD", "1,385.5")]}))
    out = fetch_rates(("USD", "GBP"), now=FRIDAY)

    assert out == FxError(FxErrorKind.MISSING_CURRENCY, "응답에 GBP 환율이 없습니다")


def test_ttl_cache_serves_same_searchdate_and_any_subset_from_one_fetch(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _install(monkeypatch, _by_date({"20260724": FULL_TABLE}))

    first = fetch_rates(DEFAULT_CURRENCIES, now=FRIDAY)
    second = fetch_rates(("JPY",), now=FRIDAY)
    assert isinstance(first, FxResult)
    assert isinstance(second, FxResult)
    assert second.rates == {"JPY": Decimal("8.9412")}
    assert len(seen) == 1

    # Past the TTL the same searchdate is fetched again.
    # TTL이 지나면 같은 searchdate를 다시 조회한다.
    expired = time.monotonic() + settings.fx_cache_ttl_s + 1
    monkeypatch.setattr(time, "monotonic", lambda: expired)
    fetch_rates(("USD",), now=FRIDAY)
    assert len(seen) == 2


# S30 review 7: httpx's own 'HTTP Request: GET <url>' INFO line carries authkey; the
# module pins that logger to WARNING even after something (ANTHROPIC_LOG=info) raised it.
# S30 리뷰 7: httpx 자체의 'HTTP Request: GET <url>' INFO 줄에 authkey가 실린다. 무언가
# (ANTHROPIC_LOG=info)가 올려 놓은 뒤에도 모듈이 그 로거를 WARNING으로 고정한다.
def test_httpx_request_log_never_carries_the_key(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="httpx")
    assert logging.getLogger("httpx").level == logging.INFO
    _install(monkeypatch, _by_date({"20260724": FULL_TABLE}))

    out = fetch_rates(("USD",), now=FRIDAY)

    assert isinstance(out, FxResult)
    assert logging.getLogger("httpx").level == logging.WARNING
    assert not [r for r in caplog.records if r.name == "httpx" and r.levelno < logging.WARNING]
    assert all(SENTINEL not in record.getMessage() for record in caplog.records)


def test_key_never_appears_in_messages_or_logs(
    fx_env: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers: list[Handler] = [
        _raising(httpx.ReadTimeout("slow")),
        _raising(httpx.ConnectError("down")),
        lambda request: httpx.Response(500, text=f"echo {request.url}"),
        lambda request: httpx.Response(200, json=[{"result": 3}]),
        lambda request: httpx.Response(200, content=b"<html>"),
        _by_date({"20260724": FULL_TABLE}),
    ]
    outcomes: list[FxResult | FxError] = []
    for handler in handlers:
        monkeypatch.setattr(fx, "_cache", {})
        _install(monkeypatch, handler)
        outcomes.append(fetch_rates(DEFAULT_CURRENCIES, now=FRIDAY))

    assert len(outcomes) == len(handlers)
    for out in outcomes:
        assert SENTINEL not in repr(out)
    assert fx_env.calls
    assert SENTINEL not in repr(fx_env.calls)
    # Only searchdate / result / kind style fields are logged — never a URL or key.
    # searchdate / result / kind 류 필드만 로깅한다 — URL도 키도 없다.
    for _event, kw in fx_env.calls:
        assert "url" not in kw
        assert "authkey" not in kw
        assert not any("koreaexim.go.kr" in str(value) for value in kw.values())
