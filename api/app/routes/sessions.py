"""Session history endpoints — sidebar list, detail, soft delete.

세션 이력 엔드포인트 — 사이드바 목록·상세·soft delete.
Contract: webapp-plan §7. Others' resources → 403 (webapp-plan §5).
계약: webapp-plan §7. 타인 자원 → 403 (webapp-plan §5).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from api.app.core.deps import CurrentUser, SessionDep
from api.app.core.errors import ApiError
from api.app.db.models import ChatSession, Message
from api.app.schemas.chat import (
    MessageOut,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummary,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _owned_session(
    session_id: uuid.UUID, current: CurrentUser, session: SessionDep
) -> ChatSession:
    chat = await session.get(ChatSession, session_id)
    # Foreign, deleted, and missing sessions are indistinguishable — 404,
    # never 403: existence is not revealed (serving-plan §9, 2026-07-08).
    # 타인·삭제·미존재 세션은 구분 불가 — 403이 아니라 404. 존재를 노출하지
    # 않는다 (serving-plan §9, 2026-07-08).
    if chat is None or chat.status == "deleted" or chat.user_id != current.id:
        raise ApiError(404, "not_found", "세션을 찾을 수 없습니다.")
    return chat


@router.get("")
async def list_sessions(current: CurrentUser, session: SessionDep) -> SessionListResponse:
    rows = (
        (
            await session.execute(
                select(ChatSession)
                .where(ChatSession.user_id == current.id, ChatSession.status != "deleted")
                .order_by(ChatSession.last_message_at.desc().nulls_last())
            )
        )
        .scalars()
        .all()
    )
    return SessionListResponse(
        sessions=[
            SessionSummary(
                id=row.id,
                title=row.title,
                last_message_at=row.last_message_at,
                message_count=row.message_count,
            )
            for row in rows
        ]
    )


@router.get("/{session_id}")
async def get_session_detail(
    session_id: uuid.UUID, current: CurrentUser, session: SessionDep
) -> SessionDetailResponse:
    chat = await _owned_session(session_id, current, session)
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.session_id == chat.id, Message.deleted_at.is_(None))
                .order_by(Message.sequence_no)
            )
        )
        .scalars()
        .all()
    )
    return SessionDetailResponse(
        id=chat.id,
        title=chat.title,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                metadata=m.meta,
                created_at=m.created_at,
            )
            for m in rows
            if m.role in ("user", "assistant")
        ],
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, current: CurrentUser, session: SessionDep) -> None:
    chat = await _owned_session(session_id, current, session)
    # Soft delete (webapp-plan §7) — history stays for owner-side analysis.
    # soft delete (webapp-plan §7) — 기록은 owner 분석용으로 남는다.
    chat.status = "deleted"
    chat.updated_at = datetime.now(UTC)
    await session.commit()
