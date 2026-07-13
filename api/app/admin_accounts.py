"""Account administration operations shared by admin routes.

관리자 라우트가 사용하는 계정 관리 작업.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.security import hash_password
from api.app.db.models import User


class AdminAccountNotFoundError(Exception):
    """Raised when the requested account does not exist.

    요청한 계정이 없을 때 발생한다.
    """


class AdminAccountPermissionError(Exception):
    """Raised when the actor cannot mutate the target account.

    실행자가 대상 계정을 수정할 수 없을 때 발생한다.
    """


class AdminAccountValidationError(Exception):
    """Raised when an account mutation violates an invariant.

    계정 변경이 불변 조건을 위반할 때 발생한다.
    """


@dataclass(frozen=True)
class AccountChanges:
    expires_at: datetime | None = None
    expires_at_supplied: bool = False
    status: str | None = None
    status_supplied: bool = False
    title: str | None = None
    title_supplied: bool = False


async def list_admin_users(session: AsyncSession) -> list[User]:
    """Return all accounts in stable creation order.

    모든 계정을 생성 순서가 안정적으로 유지되도록 반환한다.
    """
    return list(
        (
            await session.execute(select(User).order_by(User.created_at.asc(), User.id.asc()))
        ).scalars()
    )


async def _target_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    target = await session.get(User, user_id)
    if target is None:
        raise AdminAccountNotFoundError(user_id)
    return target


def _ensure_target_allowed(actor: User, target: User) -> None:
    if target.role == "owner" and (actor.role != "owner" or actor.id != target.id):
        raise AdminAccountPermissionError(target.id)


async def update_admin_user(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
    changes: AccountChanges,
) -> User:
    """Apply validated account fields and commit once.

    검증한 계정 필드를 적용하고 한 번만 커밋한다.
    """
    target = await _target_user(session, user_id)
    _ensure_target_allowed(actor, target)
    if changes.status_supplied and changes.status == "suspended" and target.id == actor.id:
        raise AdminAccountValidationError("자기 자신을 정지할 수 없습니다.")
    if changes.expires_at_supplied and changes.expires_at is None and target.role != "owner":
        raise AdminAccountValidationError("owner 외 계정의 임기는 비워둘 수 없습니다.")

    if changes.expires_at_supplied:
        target.expires_at = changes.expires_at
    if changes.status_supplied:
        assert changes.status is not None
        target.status = changes.status
    if changes.title_supplied:
        target.title = changes.title
    await session.commit()
    return target


async def reset_admin_password(
    session: AsyncSession,
    *,
    actor: User,
    user_id: uuid.UUID,
) -> tuple[User, str]:
    """Replace one password and return its plaintext exactly once.

    비밀번호를 교체하고 평문을 정확히 한 번 반환한다.
    """
    target = await _target_user(session, user_id)
    _ensure_target_allowed(actor, target)
    temporary_password = secrets.token_urlsafe(12)
    target.password_hash = hash_password(temporary_password)
    target.must_change_password = True
    await session.commit()
    return target, temporary_password
