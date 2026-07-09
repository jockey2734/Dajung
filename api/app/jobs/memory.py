"""Weekly per-user memory update job (webapp-spec S6).

주간 사용자별 메모리 갱신 잡 (webapp-spec S6).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.config import settings
from api.app.core.logging import get_logger
from api.app.db.base import SessionLocal
from api.app.db.models import ChatSession, Message, User, UserMemory, UserMemoryHistory
from api.app.llm.anthropic_client import complete

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_JOB_ID = "weekly_user_memory"
_WINDOW_DAYS = 7


class CompleteFn(Protocol):
    def __call__(
        self,
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
    ) -> str: ...


@dataclass(frozen=True)
class MemoryJobResult:
    updated: int = 0
    skipped: int = 0
    failed: int = 0


def load_memory_prompt() -> str:
    """Load the S6 memory-update instruction from prompts/.

    prompts/의 S6 메모리 갱신 지시문을 읽는다.
    """
    return (settings.prompts_dir / "memory_update.md").read_text(encoding="utf-8").strip()


async def update_all_user_memory(
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
    complete_fn: CompleteFn = complete,
) -> MemoryJobResult:
    """Run the weekly memory update for active users, isolating per-user failures.

    active 사용자 전체의 주간 메모리를 갱신하되 사용자별 실패를 격리한다.
    """
    async with session_factory() as session:
        result = await session.execute(select(User.id).where(User.status == "active"))
        user_ids = list(result.scalars().all())

    updated = skipped = failed = 0
    for user_id in user_ids:
        try:
            async with session_factory() as session:
                did_update = await update_user_memory(session, user_id, complete_fn=complete_fn)
            if did_update:
                updated += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001 — one user must not kill the batch
            failed += 1
            log.error("memory update failed", user_id=str(user_id), error=str(exc))

    log.info("memory update complete", updated=updated, skipped=skipped, failed=failed)
    return MemoryJobResult(updated=updated, skipped=skipped, failed=failed)


async def update_user_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    complete_fn: CompleteFn = complete,
) -> bool:
    """Update one user's memory; return False when there is no recent conversation.

    사용자 1명의 메모리를 갱신한다. 최근 대화가 없으면 False를 반환한다.
    """
    transcript = await _recent_transcript(session, user_id)
    if not transcript:
        return False

    current = await session.get(UserMemory, user_id)
    prompt = _build_prompt(current.content if current is not None else "", transcript)
    content = await asyncio.to_thread(
        complete_fn,
        settings.model_haiku,
        [],
        prompt,
        settings.max_tokens_memory,
    )
    updated_content = str(content).strip()[: settings.memory_output_chars].rstrip()
    if not updated_content:
        return False

    now = datetime.now(UTC)
    if current is not None:
        session.add(UserMemoryHistory(user_id=user_id, content=current.content))
        current.content = updated_content
        current.updated_at = now
    else:
        session.add(UserMemory(user_id=user_id, content=updated_content, updated_at=now))
    await session.commit()
    return True


async def _recent_transcript(session: AsyncSession, user_id: uuid.UUID) -> str:
    since = datetime.now(UTC) - timedelta(days=_WINDOW_DAYS)
    result = await session.execute(
        select(Message)
        .join(ChatSession, Message.session_id == ChatSession.id)
        .where(
            ChatSession.user_id == user_id,
            Message.role.in_(("user", "assistant")),
            Message.status == "completed",
            Message.deleted_at.is_(None),
            Message.created_at >= since,
        )
        .order_by(Message.created_at.desc(), Message.sequence_no.desc())
    )
    messages = list(result.scalars().all())
    remaining = settings.memory_input_chars
    lines: list[str] = []
    for message in messages:
        content = message.content.strip()
        if not content:
            continue
        line = f"[{message.created_at.isoformat()}] {message.role}: {content}"
        if len(line) > remaining:
            line = line[:remaining]
        lines.append(line)
        remaining -= len(line)
        if remaining <= 0:
            break
    return "\n".join(lines)


def _build_prompt(existing_memory: str, transcript: str) -> str:
    return (
        f"{load_memory_prompt()}\n\n"
        "기존 메모리:\n"
        f"{existing_memory.strip() or '(없음)'}\n\n"
        "최근 대화(최근순, 저장 시점에 PII 마스킹된 본문):\n"
        f"{transcript}\n\n"
        "갱신본만 출력:"
    )


def create_memory_scheduler(
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
) -> AsyncIOScheduler:
    """Create the Sunday 03:00 KST APScheduler instance for S6.

    S6의 일요일 03:00 KST APScheduler 인스턴스를 만든다.
    """
    scheduler = AsyncIOScheduler(timezone=_KST)
    scheduler.add_job(
        update_all_user_memory,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=_KST),
        kwargs={"session_factory": session_factory},
        id=_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
