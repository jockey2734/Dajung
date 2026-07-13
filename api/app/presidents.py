"""President appointment operations shared by API and CLI.

API와 CLI가 공유하는 회장 임명·인계 작업.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.app.core.account_term import is_account_expired
from api.app.db.models import PresidentTransfer, User


class PresidentTransferValidationError(Exception):
    """Raised when the requested successor is not eligible.

    요청한 후임자가 회장 임명 조건을 충족하지 못할 때 발생한다.
    """


@dataclass(frozen=True)
class PresidentTransferSummary:
    """One transfer audit row with all referenced users resolved.

    참조 사용자를 모두 해석한 회장 인계 감사 행.
    """

    transfer: PresidentTransfer
    from_user: User | None
    to_user: User
    actor: User


async def get_current_president(session: AsyncSession) -> User | None:
    """Return the current president, if one is appointed.

    임명된 현재 회장이 있으면 반환한다.
    """
    return (
        await session.execute(select(User).where(User.role == "president"))
    ).scalar_one_or_none()


async def list_president_transfers(
    session: AsyncSession,
) -> list[PresidentTransferSummary]:
    """Return permanent transfer records newest first with joined users.

    영구 인계 기록을 사용자 정보와 함께 최신순으로 반환한다.
    """
    from_user = aliased(User)
    to_user = aliased(User)
    actor = aliased(User)
    rows = (
        await session.execute(
            select(PresidentTransfer, from_user, to_user, actor)
            .outerjoin(from_user, PresidentTransfer.from_user_id == from_user.id)
            .join(to_user, PresidentTransfer.to_user_id == to_user.id)
            .join(actor, PresidentTransfer.actor_id == actor.id)
            .order_by(PresidentTransfer.created_at.desc(), PresidentTransfer.id.desc())
        )
    ).all()
    return [
        PresidentTransferSummary(transfer=row[0], from_user=row[1], to_user=row[2], actor=row[3])
        for row in rows
    ]


async def transfer_president(
    session: AsyncSession,
    *,
    actor: User,
    to_user_id: uuid.UUID,
    note: str | None,
) -> User:
    """Atomically demote the incumbent, appoint a successor, and audit it.

    현 회장 강등·후임 임명·감사 기록을 하나의 트랜잭션으로 처리한다.
    """
    target = await session.get(User, to_user_id)
    if (
        target is None
        or target.status != "active"
        or target.role != "staff"
        or is_account_expired(target.role, target.expires_at)
    ):
        raise PresidentTransferValidationError("임명 가능한 활성 운영진이 아닙니다.")

    current = await get_current_president(session)
    if actor.role == "president" and (current is None or current.id != actor.id):
        raise PresidentTransferValidationError("현재 회장만 권한을 인계할 수 있습니다.")

    try:
        if current is not None:
            current.role = "staff"
            # Release the partial unique index slot before promoting the successor.
            # 후임 승격 전에 부분 unique index의 기존 회장 자리를 비운다.
            await session.flush()

        target.role = "president"
        session.add(
            PresidentTransfer(
                from_user_id=current.id if current is not None else None,
                to_user_id=target.id,
                actor_id=actor.id,
                note=note,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return target
