"""Weekly user-memory job tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.app.core.config import settings
from api.app.db.base import Base
from api.app.db.models import ChatSession, Message, User, UserMemory, UserMemoryHistory
from api.app.jobs.memory import create_memory_scheduler, update_all_user_memory


@pytest.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed_user(session: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        password_hash="hash",
        name=email.split("@")[0],
        role="staff",
        status="active",
        profile={},
    )
    session.add(user)
    await session.flush()
    return user


def _add_turns(session: AsyncSession, user: User, *contents: str) -> None:
    chat = ChatSession(
        id=uuid.uuid4(),
        user_id=user.id,
        title="memory",
        status="active",
        last_message_at=datetime.now(UTC),
        meta={},
    )
    session.add(chat)
    for index, content in enumerate(contents, start=1):
        session.add(
            Message(
                session_id=chat.id,
                user_id=user.id,
                role="user",
                content=content,
                sequence_no=index,
                created_at=datetime.now(UTC),
            )
        )


async def test_memory_job_updates_history_skips_and_isolates_failure(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "memory_output_chars", 10)
    async with factory() as session:
        updated = await _seed_user(session, "updated@test.local")
        skipped = await _seed_user(session, "skipped@test.local")
        failing = await _seed_user(session, "failing@test.local")
        session.add(UserMemory(user_id=updated.id, content="old memory"))
        _add_turns(session, updated, "관심 질문")
        _add_turns(session, failing, "실패 질문")
        await session.commit()

    prompts: list[str] = []

    def fake_complete(
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        max_tokens: int,
    ) -> str:
        prompts.append(user_text)
        if "실패 질문" in user_text:
            raise RuntimeError("boom")
        assert "old memory" in user_text
        assert "관심 질문" in user_text
        return "new memory content"

    result = await update_all_user_memory(factory, complete_fn=fake_complete)

    assert result.updated == 1
    assert result.skipped == 1
    assert result.failed == 1
    assert len(prompts) == 2

    async with factory() as session:
        updated_memory = await session.get(UserMemory, updated.id)
        skipped_memory = await session.get(UserMemory, skipped.id)
        failing_memory = await session.get(UserMemory, failing.id)
        history = (await session.execute(select(UserMemoryHistory))).scalars().one()

    assert updated_memory is not None
    assert updated_memory.content == "new memory"
    assert skipped_memory is None
    assert failing_memory is None
    assert history.user_id == updated.id
    assert history.content == "old memory"


async def test_memory_scheduler_registers_sunday_kst_job(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    scheduler = create_memory_scheduler(factory)
    jobs = scheduler.get_jobs()

    assert len(jobs) == 1
    assert jobs[0].id == "weekly_user_memory"
    assert "cron" in str(jobs[0].trigger)
    assert "day_of_week='sun'" in str(jobs[0].trigger)
