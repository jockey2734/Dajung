"""Calendar account-term helpers.

달력 기준 계정 임기 helper 테스트.
"""

from __future__ import annotations

from datetime import UTC, datetime

from api.app.core.account_term import add_months, is_account_expired, to_utc


def test_add_months_clamps_end_of_month() -> None:
    assert add_months(datetime(2026, 1, 31, tzinfo=UTC), 1) == datetime(2026, 2, 28, tzinfo=UTC)
    assert add_months(datetime(2024, 1, 31, tzinfo=UTC), 1) == datetime(2024, 2, 29, tzinfo=UTC)
    assert add_months(datetime(2026, 8, 31, tzinfo=UTC), 7) == datetime(2027, 3, 31, tzinfo=UTC)


def test_to_utc_normalizes_sqlite_naive_values() -> None:
    naive = datetime(2026, 7, 13, 12, 0)
    assert to_utc(naive) == datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def test_owner_is_exempt_from_account_expiry() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    expired = datetime(2026, 7, 12, tzinfo=UTC)
    assert is_account_expired("owner", expired, now=now) is False
    assert is_account_expired("staff", expired, now=now) is True
    assert is_account_expired("president", expired, now=now) is True
    assert is_account_expired("staff", None, now=now) is False
