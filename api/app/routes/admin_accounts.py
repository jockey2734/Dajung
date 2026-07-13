"""Account administration routes.

계정 관리 라우트.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from api.app.admin_accounts import (
    AccountChanges,
    AdminAccountNotFoundError,
    AdminAccountPermissionError,
    AdminAccountValidationError,
    list_admin_users,
    reset_admin_password,
    update_admin_user,
)
from api.app.core.deps import AdminUser, SessionDep
from api.app.core.errors import ApiError
from api.app.schemas.admin_accounts import (
    AdminUserOut,
    AdminUserUpdate,
    TemporaryPasswordOut,
)

router = APIRouter(prefix="/admin/users", tags=["admin"])


def _translate_account_error(exc: Exception) -> ApiError:
    if isinstance(exc, AdminAccountNotFoundError):
        return ApiError(404, "user_not_found", "계정을 찾을 수 없습니다.")
    if isinstance(exc, AdminAccountPermissionError):
        return ApiError(403, "admin_required", "owner 계정은 본인만 수정할 수 있습니다.")
    return ApiError(422, "admin_user_invalid", str(exc))


@router.get("")
async def list_users(current: AdminUser, session: SessionDep) -> list[AdminUserOut]:
    return [AdminUserOut.model_validate(user) for user in await list_admin_users(session)]


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    current: AdminUser,
    session: SessionDep,
) -> AdminUserOut:
    fields = body.model_fields_set
    changes = AccountChanges(
        expires_at=body.expires_at,
        expires_at_supplied="expires_at" in fields,
        status=body.status,
        status_supplied="status" in fields,
        title=body.title,
        title_supplied="title" in fields,
    )
    try:
        target = await update_admin_user(session, actor=current, user_id=user_id, changes=changes)
    except (
        AdminAccountNotFoundError,
        AdminAccountPermissionError,
        AdminAccountValidationError,
    ) as exc:
        raise _translate_account_error(exc) from exc
    return AdminUserOut.model_validate(target)


@router.post("/{user_id}/password-reset")
async def reset_password(
    user_id: uuid.UUID,
    current: AdminUser,
    session: SessionDep,
) -> TemporaryPasswordOut:
    try:
        target, plaintext = await reset_admin_password(session, actor=current, user_id=user_id)
    except (AdminAccountNotFoundError, AdminAccountPermissionError) as exc:
        raise _translate_account_error(exc) from exc
    return TemporaryPasswordOut(user_id=target.id, temporary_password=plaintext)
