"""Semester roster lifecycle and account-term extension.

학기별 명단 생명주기와 계정 임기 연장.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.account_term import ACCOUNT_TERM_MONTHS, add_months, to_utc
from api.app.db.models import StaffSemester, User

KST = ZoneInfo("Asia/Seoul")


class RosterNotFoundError(Exception):
    """Raised when a roster row does not exist.

    명단 행이 없을 때 발생한다.
    """


class RosterUserNotFoundError(Exception):
    """Raised when a linked account does not exist.

    연결할 계정이 없을 때 발생한다.
    """


class RosterConflictError(Exception):
    """Raised for a duplicate semester/member pair.

    같은 학기·이름 조합이 중복될 때 발생한다.
    """


class RosterValidationError(Exception):
    """Raised when a patch clears a required roster field.

    PATCH가 필수 명단 필드를 비울 때 발생한다.
    """


@dataclass(frozen=True)
class RosterChanges:
    semester: str | None = None
    semester_supplied: bool = False
    department: str | None = None
    department_supplied: bool = False
    member_name: str | None = None
    member_name_supplied: bool = False
    position: str | None = None
    position_supplied: bool = False
    user_id: uuid.UUID | None = None
    user_id_supplied: bool = False


def semester_key(value: str) -> tuple[int, int]:
    """Convert a validated semester string to a sortable key.

    검증된 학기 문자열을 정렬 가능한 키로 변환한다.
    """
    year, term = value.split("-", maxsplit=1)
    return int(year), int(term)


def current_semester(now: datetime) -> tuple[int, int]:
    """Return the academic semester containing the KST timestamp.

    KST 시각이 속한 학기를 반환한다.
    """
    local = to_utc(now).astimezone(KST)
    if local.month < 3:
        return local.year - 1, 2
    if local.month < 9:
        return local.year, 1
    return local.year, 2


def semester_expiry(value: str) -> datetime:
    """Return semester start plus seven calendar months in UTC.

    학기 시작에 달력 기준 7개월을 더한 UTC 시각을 반환한다.
    """
    year, term = semester_key(value)
    start = datetime(year, 3 if term == 1 else 9, 1, tzinfo=KST)
    return add_months(start, ACCOUNT_TERM_MONTHS).astimezone(UTC)


async def list_roster(session: AsyncSession, semester: str | None) -> list[StaffSemester]:
    statement = select(StaffSemester)
    if semester is not None:
        statement = statement.where(StaffSemester.semester == semester)
    statement = statement.order_by(
        StaffSemester.semester.desc(),
        StaffSemester.department.asc(),
        StaffSemester.member_name.asc(),
        StaffSemester.id.asc(),
    )
    return list((await session.execute(statement)).scalars())


async def _extend_linked_user(
    session: AsyncSession,
    row: StaffSemester,
    *,
    now: datetime,
) -> None:
    if row.user_id is None:
        return
    user = await session.get(User, row.user_id)
    if user is None:
        raise RosterUserNotFoundError(row.user_id)
    if user.role == "owner" or semester_key(row.semester) < current_semester(now):
        return
    target = semester_expiry(row.semester)
    if user.expires_at is None or to_utc(user.expires_at) < target:
        user.expires_at = target


async def create_roster_row(
    session: AsyncSession,
    *,
    semester: str,
    department: str,
    member_name: str,
    position: str | None,
    user_id: uuid.UUID | None,
    now: datetime,
) -> StaffSemester:
    row = StaffSemester(
        semester=semester,
        department=department,
        member_name=member_name,
        position=position,
        user_id=user_id,
    )
    session.add(row)
    try:
        await _extend_linked_user(session, row, now=now)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise RosterConflictError from exc
    except Exception:
        await session.rollback()
        raise
    return row


async def update_roster_row(
    session: AsyncSession,
    *,
    roster_id: uuid.UUID,
    changes: RosterChanges,
    now: datetime,
) -> StaffSemester:
    row = await session.get(StaffSemester, roster_id)
    if row is None:
        raise RosterNotFoundError(roster_id)
    required = (
        (changes.semester_supplied, changes.semester),
        (changes.department_supplied, changes.department),
        (changes.member_name_supplied, changes.member_name),
    )
    if any(supplied and not value for supplied, value in required):
        raise RosterValidationError("필수 명단 필드는 비워둘 수 없습니다.")

    if changes.semester_supplied:
        assert changes.semester is not None
        row.semester = changes.semester
    if changes.department_supplied:
        assert changes.department is not None
        row.department = changes.department
    if changes.member_name_supplied:
        assert changes.member_name is not None
        row.member_name = changes.member_name
    if changes.position_supplied:
        row.position = changes.position
    if changes.user_id_supplied:
        row.user_id = changes.user_id

    try:
        await _extend_linked_user(session, row, now=now)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise RosterConflictError from exc
    except Exception:
        await session.rollback()
        raise
    return row


async def delete_roster_row(session: AsyncSession, roster_id: uuid.UUID) -> None:
    row = await session.get(StaffSemester, roster_id)
    if row is None:
        raise RosterNotFoundError(roster_id)
    await session.delete(row)
    await session.commit()
