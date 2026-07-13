"""Semester roster administration routes.

학기별 명단 관리 라우트.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from api.app.core.deps import AdminUser, SessionDep
from api.app.core.errors import ApiError
from api.app.roster import (
    RosterChanges,
    RosterConflictError,
    RosterNotFoundError,
    RosterUserNotFoundError,
    RosterValidationError,
    create_roster_row,
    delete_roster_row,
    list_roster,
    update_roster_row,
)
from api.app.schemas.admin_roster import (
    SEMESTER_PATTERN,
    RosterCreateRequest,
    RosterOut,
    RosterUpdateRequest,
)

router = APIRouter(prefix="/admin/roster", tags=["admin"])


def roster_now() -> datetime:
    return datetime.now(UTC)


def _roster_error(exc: Exception) -> ApiError:
    if isinstance(exc, RosterNotFoundError):
        return ApiError(404, "roster_not_found", "명단 행을 찾을 수 없습니다.")
    if isinstance(exc, RosterConflictError):
        return ApiError(409, "roster_conflict", "같은 학기에 동일한 이름이 이미 있습니다.")
    if isinstance(exc, RosterUserNotFoundError):
        return ApiError(422, "roster_user_invalid", "연결할 계정을 찾을 수 없습니다.")
    return ApiError(422, "roster_invalid", str(exc))


@router.get("")
async def get_roster(
    current: AdminUser,
    session: SessionDep,
    semester: Annotated[str | None, Query(pattern=SEMESTER_PATTERN)] = None,
) -> list[RosterOut]:
    return [RosterOut.model_validate(row) for row in await list_roster(session, semester)]


@router.post("", status_code=201)
async def add_roster_row(
    body: RosterCreateRequest,
    current: AdminUser,
    session: SessionDep,
) -> RosterOut:
    try:
        row = await create_roster_row(
            session,
            semester=body.semester,
            department=body.department,
            member_name=body.member_name,
            position=body.position,
            user_id=body.user_id,
            now=roster_now(),
        )
    except (RosterConflictError, RosterUserNotFoundError) as exc:
        raise _roster_error(exc) from exc
    return RosterOut.model_validate(row)


@router.patch("/{roster_id}")
async def edit_roster_row(
    roster_id: uuid.UUID,
    body: RosterUpdateRequest,
    current: AdminUser,
    session: SessionDep,
) -> RosterOut:
    fields = body.model_fields_set
    changes = RosterChanges(
        semester=body.semester,
        semester_supplied="semester" in fields,
        department=body.department,
        department_supplied="department" in fields,
        member_name=body.member_name,
        member_name_supplied="member_name" in fields,
        position=body.position,
        position_supplied="position" in fields,
        user_id=body.user_id,
        user_id_supplied="user_id" in fields,
    )
    try:
        row = await update_roster_row(
            session, roster_id=roster_id, changes=changes, now=roster_now()
        )
    except (
        RosterConflictError,
        RosterNotFoundError,
        RosterUserNotFoundError,
        RosterValidationError,
    ) as exc:
        raise _roster_error(exc) from exc
    return RosterOut.model_validate(row)


@router.delete("/{roster_id}", status_code=204)
async def remove_roster_row(
    roster_id: uuid.UUID,
    current: AdminUser,
    session: SessionDep,
) -> None:
    try:
        await delete_roster_row(session, roster_id)
    except RosterNotFoundError as exc:
        raise _roster_error(exc) from exc
