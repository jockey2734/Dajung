"""One-time initial-owner bootstrap service.

최초 owner 1회 부트스트랩 서비스.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db.models import User


class OwnerClaimError(Exception):
    """Base class for expected initial-owner claim failures.

    예상 가능한 최초 owner 승격 실패의 기본 예외.
    """


class OwnerAlreadyExistsError(OwnerClaimError):
    """Raised when the one-time owner slot is already occupied.

    1회용 owner 자리가 이미 사용됐을 때 발생한다.
    """


class OwnerUserNotFoundError(OwnerClaimError):
    """Raised when the claim target has not completed signup.

    승격 대상이 아직 가입하지 않았을 때 발생한다.
    """


async def claim_initial_owner(session: AsyncSession, email: str) -> User:
    """Promote one existing account when no owner exists.

    owner가 없을 때 기존 계정 하나를 승격한다.
    """
    owner_count = await session.scalar(select(func.count(User.id)).where(User.role == "owner"))
    if owner_count:
        raise OwnerAlreadyExistsError

    normalized_email = email.strip().lower()
    user = (
        await session.execute(select(User).where(User.email == normalized_email))
    ).scalar_one_or_none()
    if user is None:
        raise OwnerUserNotFoundError(normalized_email)

    user.role = "owner"
    user.expires_at = None
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return user
