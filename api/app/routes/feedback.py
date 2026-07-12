"""Per-user thumbs-up/down feedback for assistant messages.

어시스턴트 메시지에 대한 사용자별 좋아요·싫어요 피드백.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.app.core.deps import CurrentUser, SessionDep
from api.app.core.errors import ApiError
from api.app.db.models import ChatSession, Feedback, Message
from api.app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/messages", tags=["feedback"])


async def _owned_message(
    message_id: uuid.UUID, current: CurrentUser, session: SessionDep
) -> Message:
    message = (
        await session.execute(
            select(Message)
            .join(ChatSession, Message.session_id == ChatSession.id)
            .where(
                Message.id == message_id,
                Message.deleted_at.is_(None),
                ChatSession.user_id == current.id,
                ChatSession.status != "deleted",
            )
        )
    ).scalar_one_or_none()
    if message is None:
        raise ApiError(404, "not_found", "메시지를 찾을 수 없습니다.")
    return message


def _require_assistant(message: Message) -> None:
    if message.role != "assistant":
        raise ApiError(
            422,
            "feedback_not_allowed",
            "어시스턴트 메시지만 평가할 수 있습니다.",
        )


async def _find_feedback(
    message_id: uuid.UUID, current: CurrentUser, session: SessionDep
) -> Feedback | None:
    return (
        await session.execute(
            select(Feedback).where(
                Feedback.message_id == message_id,
                Feedback.user_id == current.id,
            )
        )
    ).scalar_one_or_none()


async def _save_feedback(
    message_id: uuid.UUID,
    body: FeedbackRequest,
    current: CurrentUser,
    session: SessionDep,
) -> None:
    existing = await _find_feedback(message_id, current, session)
    if existing is not None:
        existing.rating = body.rating
        existing.comment = body.comment
        await session.commit()
        return

    session.add(
        Feedback(
            message_id=message_id,
            user_id=current.id,
            rating=body.rating,
            comment=body.comment,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        # A concurrent first write may win the unique constraint. Retry as update.
        # 동시 최초 작성이 unique 제약을 먼저 선점할 수 있어 update로 재시도한다.
        await session.rollback()
        existing = await _find_feedback(message_id, current, session)
        if existing is None:
            raise
        existing.rating = body.rating
        existing.comment = body.comment
        await session.commit()


@router.put("/{message_id}/feedback")
async def put_feedback(
    message_id: uuid.UUID,
    body: FeedbackRequest,
    current: CurrentUser,
    session: SessionDep,
) -> FeedbackResponse:
    message = await _owned_message(message_id, current, session)
    _require_assistant(message)
    await _save_feedback(message.id, body, current, session)
    return FeedbackResponse(
        message_id=message.id,
        rating=body.rating,
        comment=body.comment,
    )


@router.delete("/{message_id}/feedback", status_code=204)
async def delete_feedback(
    message_id: uuid.UUID,
    current: CurrentUser,
    session: SessionDep,
) -> None:
    message = await _owned_message(message_id, current, session)
    _require_assistant(message)
    existing = await _find_feedback(message.id, current, session)
    if existing is None:
        raise ApiError(404, "not_found", "피드백을 찾을 수 없습니다.")
    await session.delete(existing)
    await session.commit()
