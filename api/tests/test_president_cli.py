"""President CLI integration tests with a file-backed synthetic database.

파일 기반 합성 DB를 사용하는 회장 관리 CLI 통합 테스트.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typer.testing import CliRunner

import api.app.cli as cli_module
from api.app.cli import app
from api.app.db.base import Base
from api.app.db.models import PresidentTransfer, User

runner = CliRunner()


@pytest.fixture
def president_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'president.db'}")

    async def setup() -> async_sessionmaker[AsyncSession]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add_all(
                [
                    User(
                        email="owner@example.com",
                        password_hash="unused",  # pragma: allowlist secret
                        name="관리자",
                        role="owner",
                        status="active",
                        profile={},
                    ),
                    User(
                        email="next@example.com",
                        password_hash="unused",  # pragma: allowlist secret
                        name="차기 회장",
                        role="staff",
                        status="active",
                        expires_at=datetime.now(UTC) + timedelta(days=180),
                        profile={},
                    ),
                ]
            )
            await session.commit()
        return factory

    factory = asyncio.run(setup())
    monkeypatch.setattr(cli_module, "_session_factory", lambda: factory)
    yield factory
    asyncio.run(engine.dispose())


def test_set_show_and_history_share_transfer_service(
    president_db: async_sessionmaker[AsyncSession],
) -> None:
    appointed = runner.invoke(app, ["president", "set", "next@example.com", "--note", "정기 임명"])
    assert appointed.exit_code == 0
    assert "차기 회장" in appointed.output

    shown = runner.invoke(app, ["president", "show"])
    assert shown.exit_code == 0
    assert "next@example.com" in shown.output

    history = runner.invoke(app, ["president", "history"])
    assert history.exit_code == 0
    assert "관리자" in history.output
    assert "차기 회장" in history.output
    assert "정기 임명" in history.output

    async def load() -> tuple[str, int]:
        async with president_db() as session:
            role = (
                await session.execute(select(User.role).where(User.email == "next@example.com"))
            ).scalar_one()
            count = len((await session.execute(select(PresidentTransfer))).scalars().all())
            return role, count

    assert asyncio.run(load()) == ("president", 1)


def test_set_rejects_unknown_email(president_db: async_sessionmaker[AsyncSession]) -> None:
    result = runner.invoke(app, ["president", "set", "missing@example.com"])

    assert result.exit_code == 1
    assert "찾을 수 없습니다" in result.output
