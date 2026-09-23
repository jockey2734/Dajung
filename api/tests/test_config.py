"""Settings defaults and env-override behavior.

설정 기본값과 환경변수 오버라이드 동작.
"""

from __future__ import annotations

import pytest

from api.app.core.config import Settings


def test_defaults_match_spec() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.model_haiku == "claude-haiku-4-5"
    assert s.model_sonnet == "claude-sonnet-5"
    assert s.model_opus == "claude-opus-5"
    assert s.router_model == "gemma4:e4b"
    assert s.rerank_threshold == 0.5
    assert s.retrieve_limit == 20
    assert s.rerank_top_k == 5
    assert s.max_retries == 2
    assert s.chunk_max_chars == 1600
    assert s.history_max_messages == 10
    assert s.history_message_max_chars == 500
    assert s.history_total_max_chars == 4000
    assert s.web_search_max_uses == 3
    assert s.fx_timeout_s == 5.0
    assert s.fx_cache_ttl_s == 3600
    assert s.fx_lookback_days == 10
    assert s.fx_de_minimis_usd == 150
    assert s.fx_de_minimis_usd_us == 200


def test_env_prefix_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAJUNG_RERANK_THRESHOLD", "0.7")
    monkeypatch.setenv("DAJUNG_COLLECTION", "dajung_test")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.rerank_threshold == 0.7
    assert s.collection == "dajung_test"


def test_secrets_default_empty() -> None:
    # Keys must come from env only — empty by default, never hardcoded.
    # 키는 환경변수로만 — 기본값은 빈 문자열, 하드코딩 금지.
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.anthropic_api_key == ""
    assert s.qdrant_api_key == ""
    assert s.koreaexim_api_key == ""
