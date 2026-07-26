"""KST clock and Dajung academic-semester context.

KST 시계와 다정 학기 컨텍스트.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from api.app.core.account_term import to_utc

KST = ZoneInfo("Asia/Seoul")

_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")


def now_kst() -> datetime:
    """Return the current timezone-aware KST datetime.

    현재 KST aware datetime을 반환한다.
    """
    return datetime.now(KST)


def _as_kst(moment: datetime) -> datetime:
    return to_utc(moment).astimezone(KST)


def current_semester(now: datetime) -> tuple[int, int]:
    """Return the academic semester containing the KST timestamp.

    KST 시각이 속한 학기를 반환한다.
    """
    local = _as_kst(now)
    if local.month < 3:
        return local.year - 1, 2
    if local.month < 9:
        return local.year, 1
    return local.year, 2


def semester_label(now: datetime) -> str:
    """Return the current semester as a YYYY-N label.

    현재 학기를 YYYY-N 문자열로 반환한다.
    """
    year, term = current_semester(now)
    return f"{year}-{term}"


def academic_phase(now: datetime) -> str:
    """Return the fixed month-based academic phase.

    월 기준으로 고정된 학사 국면을 반환한다.
    """
    month = _as_kst(now).month
    if month < 3:
        return "겨울방학"
    if month < 7:
        return "1학기 학기중"
    if month < 9:
        return "여름방학"
    return "2학기 학기중"


def date_context(now: datetime | None = None) -> str:
    """Render the current date, semester, and phase for model prompts.

    모델 프롬프트용 현재 날짜·학기·국면 문자열을 만든다.
    """
    local = now_kst() if now is None else _as_kst(now)
    return (
        f"오늘: {local.year}년 {local.month}월 {local.day}일 "
        f"({_WEEKDAYS[local.weekday()]}) · 현재 학기: {semester_label(local)} · "
        f"{academic_phase(local)}"
    )
