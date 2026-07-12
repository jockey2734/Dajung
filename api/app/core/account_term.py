"""Calendar-based account-term calculations.

달력 기준 계정 임기 계산.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime

ACCOUNT_TERM_MONTHS = 7
ACCOUNT_EXPIRED_MESSAGE = "계정 임기가 만료되었습니다. 회장에게 연장을 요청해 주세요."


def to_utc(moment: datetime) -> datetime:
    """Normalize SQLite-naive and PostgreSQL-aware datetimes to UTC.

    SQLite naive·PostgreSQL aware datetime을 UTC로 정규화한다.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def add_months(moment: datetime, months: int) -> datetime:
    """Add calendar months and clamp the day to the destination month end.

    달력 월을 더하고 날짜를 도착 월의 말일로 제한한다.
    """
    month_index = moment.year * 12 + (moment.month - 1) + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def is_account_expired(
    role: str,
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether a non-owner account has passed its stored term.

    owner가 아닌 계정이 저장된 임기를 지났는지 반환한다.
    """
    if role == "owner" or expires_at is None:
        return False
    current = now or datetime.now(UTC)
    return to_utc(expires_at) < to_utc(current)
