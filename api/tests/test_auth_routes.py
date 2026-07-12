"""End-to-end auth route tests over in-memory SQLite.

인메모리 SQLite 위에서 도는 인증 라우트 엔드투엔드 테스트.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.app.core.account_term import ACCOUNT_TERM_MONTHS, add_months, to_utc
from api.app.core.config import settings
from api.app.core.ratelimit import limiter
from api.app.core.security import create_access_token, hash_invitation_code, hash_password
from api.app.db.base import Base, get_session
from api.app.db.models import InvitationCode, User
from api.app.main import create_app

GOOD_CODE = "DAJUNG-CODE-1"


@pytest.fixture(autouse=True)
def _fast_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "bcrypt_rounds", 4)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")


@pytest.fixture
async def harness() -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    limiter.reset()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory, app
    await engine.dispose()


async def _seed_code(
    factory: async_sessionmaker[AsyncSession],
    code: str = GOOD_CODE,
    expires_in_days: int = 7,
    used: bool = False,
) -> None:
    async with factory() as session:
        session.add(
            InvitationCode(
                code_hash=hash_invitation_code(code),
                expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
                used_at=datetime.now(UTC) if used else None,
            )
        )
        await session.commit()


async def _seed_user(
    factory: async_sessionmaker[AsyncSession],
    email: str = "unha@example.com",
    password: str = "correct-password",
    status: str = "active",
    role: str = "staff",
    expires_at: datetime | None = None,
) -> User:
    async with factory() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            name="운하",
            role=role,
            status=status,
            profile={},
            expires_at=expires_at,
        )
        session.add(user)
        await session.commit()
        return user


def _signup_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "email": "new@example.com",
        "password": "long-enough-pw",  # pragma: allowlist secret
        "name": "새 운영진",
        "invitation_code": GOOD_CODE,
    }
    body.update(overrides)
    return body


class TestSignup:
    async def test_happy_path_creates_user_and_consumes_code(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_code(factory)
        response = await client.post("/auth/signup", json=_signup_body())
        assert response.status_code == 201
        user_id = uuid.UUID(response.json()["user_id"])

        async with factory() as session:
            user = await session.get(User, user_id)
            assert user is not None and user.role == "staff"
            assert user.expires_at is not None
            expected = add_months(datetime.now(UTC), ACCOUNT_TERM_MONTHS)
            assert abs((to_utc(user.expires_at) - expected).total_seconds()) < 5
            codes = (await session.execute(InvitationCode.__table__.select())).all()
            assert codes[0].used_at is not None
            assert codes[0].used_by == user_id

    async def test_unknown_code_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, _, _ = harness
        response = await client.post("/auth/signup", json=_signup_body(invitation_code="WRONG"))
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_code"

    async def test_used_code_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_code(factory, used=True)
        response = await client.post("/auth/signup", json=_signup_body())
        assert response.status_code == 400

    async def test_expired_code_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_code(factory, expires_in_days=-1)
        response = await client.post("/auth/signup", json=_signup_body())
        assert response.status_code == 400

    async def test_duplicate_email_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_code(factory)
        await _seed_code(factory, code="DAJUNG-CODE-2")
        await _seed_user(factory, email="new@example.com")
        response = await client.post("/auth/signup", json=_signup_body())
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "email_exists"


class TestSignin:
    async def test_happy_path_returns_token_and_user(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_user(factory)
        response = await client.post(
            "/auth/signin",
            json={
                "email": "unha@example.com",
                "password": "correct-password",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["user"]["email"] == "unha@example.com"
        assert payload["access_token"].count(".") == 2

    async def test_wrong_password_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_user(factory)
        response = await client.post(
            "/auth/signin",
            json={"email": "unha@example.com", "password": "nope"},  # pragma: allowlist secret
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "bad_credentials"

    async def test_suspended_user_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_user(factory, status="suspended")
        response = await client.post(
            "/auth/signin",
            json={
                "email": "unha@example.com",
                "password": "correct-password",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 401

    async def test_expired_user_gets_explicit_error(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_user(factory, expires_at=datetime.now(UTC) - timedelta(days=1))

        response = await client.post(
            "/auth/signin",
            json={
                "email": "unha@example.com",
                "password": "correct-password",  # pragma: allowlist secret
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "account_expired"

    async def test_owner_ignores_account_expiry(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_user(
            factory,
            role="owner",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )

        response = await client.post(
            "/auth/signin",
            json={
                "email": "unha@example.com",
                "password": "correct-password",  # pragma: allowlist secret
            },
        )

        assert response.status_code == 200

    async def test_lockout_after_five_failures(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_user(factory)
        for _ in range(5):
            bad = await client.post(
                "/auth/signin",
                json={
                    "email": "unha@example.com",
                    "password": "nope",  # pragma: allowlist secret
                },
            )
            assert bad.status_code == 401
        # Correct password no longer helps — the email is locked (SECURITY.md §3).
        # 올바른 비밀번호여도 소용없다 — 이메일이 잠겼다 (SECURITY.md §3).
        locked = await client.post(
            "/auth/signin",
            json={
                "email": "unha@example.com",
                "password": "correct-password",  # pragma: allowlist secret
            },
        )
        assert locked.status_code == 429
        assert locked.json()["error"]["code"] == "locked_out"


class TestMe:
    async def test_me_roundtrip(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        await _seed_user(factory)
        signin = await client.post(
            "/auth/signin",
            json={
                "email": "unha@example.com",
                "password": "correct-password",  # pragma: allowlist secret
            },
        )
        token = signin.json()["access_token"]
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == "unha@example.com"

    async def test_expired_token_recovers_after_extension(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, factory, _ = harness
        user = await _seed_user(factory, expires_at=datetime.now(UTC) - timedelta(days=1))
        token = create_access_token(user.id, user.email, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        expired = await client.get("/auth/me", headers=headers)
        assert expired.status_code == 401
        assert expired.json()["error"]["code"] == "account_expired"

        async with factory() as session:
            stored = await session.get(User, user.id)
            assert stored is not None
            stored.expires_at = datetime.now(UTC) + timedelta(days=1)
            await session.commit()

        assert (await client.get("/auth/me", headers=headers)).status_code == 200

    async def test_me_without_token_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, _, _ = harness
        response = await client.get("/auth/me")
        assert response.status_code == 401

    async def test_me_with_garbage_token_rejected(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, _, _ = harness
        response = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "token_invalid"


class TestRateLimitAndHealth:
    async def test_ip_rate_limit_returns_contract_error(
        self,
        harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, _, _ = harness
        monkeypatch.setattr(settings, "rate_limit_ip", "3/minute")
        for _ in range(3):
            await client.post(
                "/auth/signin",
                json={
                    "email": "x@example.com",
                    "password": "whatever",  # pragma: allowlist secret
                },
            )
        blocked = await client.post(
            "/auth/signin",
            json={
                "email": "x@example.com",
                "password": "whatever",  # pragma: allowlist secret
            },
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "rate_limited"

    async def test_healthz_reports_db(
        self, harness: tuple[AsyncClient, async_sessionmaker[AsyncSession], FastAPI]
    ) -> None:
        client, _, _ = harness
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["db"] == "ok"
