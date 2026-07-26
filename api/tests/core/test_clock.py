"""KST date, academic-semester, and prompt-context calculations.

KST 날짜·학기·프롬프트 컨텍스트 계산.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from api.app.core.clock import (
    KST,
    academic_phase,
    current_semester,
    date_context,
    semester_label,
)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (datetime(2026, 2, 28, tzinfo=KST), (2025, 2)),
        (datetime(2026, 3, 1, tzinfo=KST), (2026, 1)),
        (datetime(2026, 8, 31, tzinfo=KST), (2026, 1)),
        (datetime(2026, 9, 1, tzinfo=KST), (2026, 2)),
    ],
)
def test_current_semester_boundaries(moment: datetime, expected: tuple[int, int]) -> None:
    assert current_semester(moment) == expected
    assert semester_label(moment) == f"{expected[0]}-{expected[1]}"


@pytest.mark.parametrize(
    ("month", "expected"),
    [
        (1, "겨울방학"),
        (3, "1학기 학기중"),
        (7, "여름방학"),
        (9, "2학기 학기중"),
    ],
)
def test_academic_phase_by_month(month: int, expected: str) -> None:
    assert academic_phase(datetime(2026, month, 15, tzinfo=KST)) == expected


def test_date_context_exact_korean_format() -> None:
    moment = datetime(2026, 7, 26, 9, 30, tzinfo=KST)
    assert date_context(moment) == "오늘: 2026년 7월 26일 (일) · 현재 학기: 2026-1 · 여름방학"
