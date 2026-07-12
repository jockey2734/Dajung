"""Invitation-code lifecycle operations shared by the owner CLI.

owner CLI가 사용하는 통과번호 생명주기 작업.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.security import hash_invitation_code
from api.app.db.models import InvitationCode

InvitationStatus = Literal["활성", "만료", "사용됨"]


@dataclass(frozen=True)
class CreatedInvitation:
    """One newly issued code whose plaintext exists only in memory.

    평문이 메모리에만 존재하는 신규 발급 코드.
    """

    id: uuid.UUID
    code: str
    note: str | None
    expires_at: datetime


@dataclass(frozen=True)
class InvitationSummary:
    """Safe invitation metadata that never contains plaintext.

    평문을 포함하지 않는 안전한 통과번호 메타데이터.
    """

    id: uuid.UUID
    note: str | None
    expires_at: datetime
    status: InvitationStatus
    used_at: datetime | None


class InvitationPrefixNotFoundError(Exception):
    """Raised when no invitation ID starts with the supplied prefix.

    입력 prefix로 시작하는 통과번호 ID가 없을 때 발생한다.
    """


class InvitationPrefixAmbiguousError(Exception):
    """Raised when an invitation ID prefix matches multiple rows.

    통과번호 ID prefix가 여러 행과 일치할 때 발생한다.
    """


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _status(row: InvitationCode, now: datetime) -> InvitationStatus:
    if row.used_at is not None:
        return "사용됨"
    if _as_utc(row.expires_at) <= now:
        return "만료"
    return "활성"


def _summary(row: InvitationCode, now: datetime) -> InvitationSummary:
    return InvitationSummary(
        id=row.id,
        note=row.note,
        expires_at=_as_utc(row.expires_at),
        status=_status(row, now),
        used_at=_as_utc(row.used_at) if row.used_at is not None else None,
    )


async def create_invitation(
    session: AsyncSession, *, note: str | None, days: int
) -> CreatedInvitation:
    """Create a single-use code and persist only its SHA-256 digest.

    단일 사용 코드를 만들고 SHA-256 해시만 저장한다.
    """
    code = secrets.token_urlsafe(9)
    expires_at = datetime.now(UTC) + timedelta(days=days)
    row = InvitationCode(
        code_hash=hash_invitation_code(code),
        note=note,
        expires_at=expires_at,
    )
    session.add(row)
    await session.commit()
    return CreatedInvitation(
        id=row.id,
        code=code,
        note=row.note,
        expires_at=expires_at,
    )


async def list_invitations(session: AsyncSession) -> list[InvitationSummary]:
    """Return newest-first invitation metadata with derived status.

    통과번호 메타데이터를 최신순 상태와 함께 반환한다.
    """
    rows = (
        (
            await session.execute(
                select(InvitationCode).order_by(
                    InvitationCode.created_at.desc(), InvitationCode.id.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    return [_summary(row, now) for row in rows]


async def revoke_invitation(session: AsyncSession, prefix: str) -> InvitationSummary:
    """Expire the one invitation matching an ID prefix without deleting it.

    ID prefix와 일치하는 통과번호 하나를 삭제하지 않고 즉시 만료한다.
    """
    rows = (await session.execute(select(InvitationCode))).scalars().all()
    normalized = prefix.strip().lower()
    matches = [row for row in rows if str(row.id).lower().startswith(normalized)]
    if not matches:
        raise InvitationPrefixNotFoundError(prefix)
    if len(matches) > 1:
        raise InvitationPrefixAmbiguousError(prefix)

    row = matches[0]
    now = datetime.now(UTC)
    row.expires_at = now
    await session.commit()
    return _summary(row, now)
