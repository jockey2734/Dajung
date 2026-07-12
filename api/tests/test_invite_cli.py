"""Invitation-code CLI integration tests with synthetic SQLite data.

합성 SQLite 데이터를 사용하는 통과번호 CLI 통합 테스트.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from typer.testing import CliRunner

import api.app.cli as cli_module
from api.app.cli import app
from api.app.core.config import settings
from api.app.core.ratelimit import limiter
from api.app.core.security import hash_invitation_code
from api.app.db.base import Base, get_session
from api.app.db.models import InvitationCode
from api.app.main import create_app

runner = CliRunner()
CODE_PATTERN = re.compile(r"통과번호: ([A-Za-z0-9_-]{12})")


@pytest.fixture
def invite_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'invite.db'}")

    async def create_tables() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(cli_module, "_session_factory", lambda: factory, raising=False)
    monkeypatch.setattr(settings, "bcrypt_rounds", 4)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    yield factory
    asyncio.run(engine.dispose())


def _extract_code(output: str) -> str:
    match = CODE_PATTERN.search(output)
    assert match is not None
    return match.group(1)


def _load_codes(factory: async_sessionmaker[AsyncSession]) -> list[InvitationCode]:
    async def load() -> list[InvitationCode]:
        async with factory() as session:
            return list((await session.execute(select(InvitationCode))).scalars().all())

    return asyncio.run(load())


def _signup(factory: async_sessionmaker[AsyncSession], code: str) -> Response:
    test_credential = "long-enough-pw"

    async def submit() -> Response:
        api: FastAPI = create_app()

        async def override_session() -> AsyncIterator[AsyncSession]:
            async with factory() as session:
                yield session

        api.dependency_overrides[get_session] = override_session
        limiter.reset()
        async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as client:
            return await client.post(
                "/auth/signup",
                json={
                    "email": f"new-{uuid.uuid4().hex[:8]}@example.com",
                    "password": test_credential,
                    "name": "신규 운영진",
                    "invitation_code": code,
                },
            )

    return asyncio.run(submit())


def _seed_codes(factory: async_sessionmaker[AsyncSession], rows: list[InvitationCode]) -> None:
    async def seed() -> None:
        async with factory() as session:
            session.add_all(rows)
            await session.commit()

    asyncio.run(seed())


def test_create_prints_once_stores_hash_and_allows_signup(
    invite_db: async_sessionmaker[AsyncSession],
) -> None:
    result = runner.invoke(app, ["invite", "create", "--note", "신규", "--days", "7"])

    assert result.exit_code == 0
    code = _extract_code(result.output)
    assert result.output.count(code) == 1
    rows = _load_codes(invite_db)
    assert len(rows) == 1
    assert rows[0].code_hash == hash_invitation_code(code)
    assert code not in rows[0].code_hash
    assert code not in (rows[0].note or "")
    assert _signup(invite_db, code).status_code == 201


def test_create_with_zero_days_is_immediately_expired(
    invite_db: async_sessionmaker[AsyncSession],
) -> None:
    result = runner.invoke(app, ["invite", "create", "--days", "0"])

    assert result.exit_code == 0
    assert _signup(invite_db, _extract_code(result.output)).status_code == 400


def test_list_shows_active_expired_and_used(
    invite_db: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    _seed_codes(
        invite_db,
        [
            InvitationCode(
                id=uuid.UUID("11111111-0000-0000-0000-000000000001"),
                code_hash=hash_invitation_code("active"),
                note="활성 코드",
                expires_at=now + timedelta(days=1),
            ),
            InvitationCode(
                id=uuid.UUID("22222222-0000-0000-0000-000000000002"),
                code_hash=hash_invitation_code("expired"),
                note="만료 코드",
                expires_at=now - timedelta(days=1),
            ),
            InvitationCode(
                id=uuid.UUID("33333333-0000-0000-0000-000000000003"),
                code_hash=hash_invitation_code("used"),
                note="사용 코드",
                expires_at=now + timedelta(days=1),
                used_at=now,
            ),
        ],
    )

    result = runner.invoke(app, ["invite", "list"])

    assert result.exit_code == 0
    assert "평문 복원 불가" in result.output
    for prefix, note, status in (
        ("11111111", "활성 코드", "활성"),
        ("22222222", "만료 코드", "만료"),
        ("33333333", "사용 코드", "사용됨"),
    ):
        assert prefix in result.output
        assert note in result.output
        assert status in result.output


def test_revoke_expires_without_deleting(
    invite_db: async_sessionmaker[AsyncSession],
) -> None:
    create_result = runner.invoke(app, ["invite", "create", "--days", "7"])
    code = _extract_code(create_result.output)
    row = _load_codes(invite_db)[0]

    revoke_result = runner.invoke(app, ["invite", "revoke", str(row.id)[:8]])

    assert revoke_result.exit_code == 0
    assert str(row.id)[:8] in revoke_result.output
    remaining = _load_codes(invite_db)
    assert len(remaining) == 1
    expires_at = remaining[0].expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    assert expires_at <= datetime.now(UTC)
    assert _signup(invite_db, code).status_code == 400


def test_revoke_rejects_ambiguous_prefix(
    invite_db: async_sessionmaker[AsyncSession],
) -> None:
    future = datetime.now(UTC) + timedelta(days=7)
    _seed_codes(
        invite_db,
        [
            InvitationCode(
                id=uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                code_hash=hash_invitation_code("first"),
                expires_at=future,
            ),
            InvitationCode(
                id=uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002"),
                code_hash=hash_invitation_code("second"),
                expires_at=future,
            ),
        ],
    )

    result = runner.invoke(app, ["invite", "revoke", "aaaaaaaa"])

    assert result.exit_code == 1
    assert "모호" in result.output
    for row in _load_codes(invite_db):
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        assert expires_at > datetime.now(UTC)
