"""President administration routes.

회장 권한 관리 라우트.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.app.core.deps import AdminUser, SessionDep
from api.app.core.errors import ApiError
from api.app.db.models import User
from api.app.presidents import (
    PresidentTransferSummary,
    PresidentTransferValidationError,
    get_current_president,
    list_president_transfers,
    transfer_president,
)
from api.app.schemas.admin import (
    PresidentTransferOut,
    PresidentTransferRequest,
    PresidentUserOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_out(user: User) -> PresidentUserOut:
    return PresidentUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        title=user.title,
        expires_at=user.expires_at,
    )


def _transfer_out(row: PresidentTransferSummary) -> PresidentTransferOut:
    return PresidentTransferOut(
        id=row.transfer.id,
        from_user=_user_out(row.from_user) if row.from_user is not None else None,
        to_user=_user_out(row.to_user),
        actor=_user_out(row.actor),
        note=row.transfer.note,
        created_at=row.transfer.created_at,
    )


@router.post("/president/transfer")
async def appoint_president(
    body: PresidentTransferRequest,
    current: AdminUser,
    session: SessionDep,
) -> PresidentUserOut:
    try:
        target = await transfer_president(
            session,
            actor=current,
            to_user_id=body.to_user_id,
            note=body.note,
        )
    except PresidentTransferValidationError as exc:
        raise ApiError(422, "president_transfer_invalid", str(exc)) from exc
    return _user_out(target)


@router.get("/president")
async def current_president(current: AdminUser, session: SessionDep) -> PresidentUserOut | None:
    president = await get_current_president(session)
    return _user_out(president) if president is not None else None


@router.get("/president/transfers")
async def president_transfer_history(
    current: AdminUser, session: SessionDep
) -> list[PresidentTransferOut]:
    return [_transfer_out(row) for row in await list_president_transfers(session)]
