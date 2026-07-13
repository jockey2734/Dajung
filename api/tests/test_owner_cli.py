"""Initial-owner CLI integration tests with a synthetic database.

합성 DB를 사용하는 최초 owner CLI 통합 테스트.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typer.testing import CliRunner

import api.app.cli as cli_module
from api.app.cli import app
from api.app.core.config import settings
from api.app.core.security import create_access_token
from api.app.db.base import Base, get_session
from api.app.db.models import User
from api.app.main import create_app

runner = CliRunner()


@pytest.fixture
def owner_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'owner.db'}")

    async def setup() -> async_sessionmaker[AsyncSession]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                User(
                    email="first@example.com",
                    password_hash="unused",  # pragma: allowlist secret
                    name="최초 가입자",
                    role="staff",
                    status="active",
                    expires_at=datetime.now(UTC) + timedelta(days=180),
                    profile={},
                )
            )
            await session.commit()
        return factory

    factory = asyncio.run(setup())
    monkeypatch.setattr(cli_module, "_session_factory", lambda: factory)
    monkeypatch.setattr(settings, "jwt_secret", "owner-claim-test-secret-32-bytes")
    yield factory
    asyncio.run(engine.dispose())


def test_claim_promotes_only_user_and_unlocks_admin_api(
    owner_db: async_sessionmaker[AsyncSession],
) -> None:
    async def load_identity() -> tuple[uuid.UUID, str, str]:
        async with owner_db() as session:
            user = (await session.execute(select(User))).scalar_one()
            return user.id, user.email, user.role

    user_id, email, previous_role = asyncio.run(load_identity())
    token = create_access_token(user_id, email, previous_role)

    result = runner.invoke(app, ["owner", "claim", " FIRST@example.com "])

    assert result.exit_code == 0
    assert "최초 가입자 <first@example.com>" in result.output

    async def verify() -> tuple[str, datetime | None, int]:
        api = create_app()

        async def override_session() -> AsyncIterator[AsyncSession]:
            async with owner_db() as session:
                yield session

        api.dependency_overrides[get_session] = override_session
        async with owner_db() as session:
            user = (await session.execute(select(User))).scalar_one()
            role = user.role
            expires_at = user.expires_at
        transport = ASGITransport(app=api)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/admin/docs/folders",
                headers={"Authorization": f"Bearer {token}"},
            )
        return role, expires_at, response.status_code

    assert asyncio.run(verify()) == ("owner", None, 200)


def test_claim_rejects_when_owner_already_exists(
    owner_db: async_sessionmaker[AsyncSession],
) -> None:
    first = runner.invoke(app, ["owner", "claim", "first@example.com"])
    second = runner.invoke(app, ["owner", "claim", "first@example.com"])

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "이미 owner 계정이 존재합니다" in second.output


def test_claim_rejects_unknown_email(owner_db: async_sessionmaker[AsyncSession]) -> None:
    result = runner.invoke(app, ["owner", "claim", "missing@example.com"])

    assert result.exit_code == 1
    assert "사용자를 찾을 수 없습니다" in result.output
