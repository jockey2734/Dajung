"""Invitation administration routes backed by the CLI service.

CLI 서비스로 동작하는 통과번호 관리 라우트.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from api.app.core.deps import AdminUser, SessionDep
from api.app.core.errors import ApiError
from api.app.invitations import (
    InvitationPrefixNotFoundError,
    InvitationSummary,
    create_invitation,
    list_invitations,
    revoke_invitation,
)
from api.app.schemas.admin_invitations import (
    InvitationCreatedOut,
    InvitationCreateRequest,
    InvitationOut,
)

router = APIRouter(prefix="/admin/invitations", tags=["admin"])


def _invitation_out(row: InvitationSummary) -> InvitationOut:
    return InvitationOut(
        id=row.id,
        note=row.note,
        expires_at=row.expires_at,
        status=row.status,
        used_at=row.used_at,
    )


@router.get("")
async def get_invitations(current: AdminUser, session: SessionDep) -> list[InvitationOut]:
    return [_invitation_out(row) for row in await list_invitations(session)]


@router.post("", status_code=201)
async def issue_invitation(
    body: InvitationCreateRequest,
    current: AdminUser,
    session: SessionDep,
) -> InvitationCreatedOut:
    created = await create_invitation(session, note=body.note, days=body.days)
    return InvitationCreatedOut(
        id=created.id,
        code=created.code,
        note=created.note,
        expires_at=created.expires_at,
    )


@router.post("/{invitation_id}/revoke")
async def revoke_invitation_code(
    invitation_id: uuid.UUID,
    current: AdminUser,
    session: SessionDep,
) -> InvitationOut:
    try:
        revoked = await revoke_invitation(session, str(invitation_id))
    except InvitationPrefixNotFoundError as exc:
        raise ApiError(404, "invitation_not_found", "통과번호를 찾을 수 없습니다.") from exc
    return _invitation_out(revoked)
