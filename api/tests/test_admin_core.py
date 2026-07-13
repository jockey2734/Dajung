"""President administration integration tests with synthetic users.

합성 사용자로 검증하는 회장 권한 관리 통합 테스트.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token
from api.app.db.models import PresidentTransfer, User
from api.app.presidents import transfer_president

ApiHarness = tuple[AsyncClient, async_sessionmaker[AsyncSession], object]


async def _seed_user(
    factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    name: str,
    role: str,
    status: str = "active",
    expires_at: datetime | None = None,
) -> User:
    if expires_at is None and role != "owner":
        expires_at = datetime.now(UTC) + timedelta(days=180)
    user = User(
        email=email,
        password_hash="not-used",  # pragma: allowlist secret
        name=name,
        role=role,
        status=status,
        expires_at=expires_at,
        profile={},
    )
    async with factory() as session:
        session.add(user)
        await session.commit()
    return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.email, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_database_rejects_two_presidents(api_harness: ApiHarness) -> None:
    _, factory, _ = api_harness
    future = datetime.now(UTC) + timedelta(days=180)
    async with factory() as session:
        session.add_all(
            [
                User(
                    email="first@example.com",
                    password_hash="unused",  # pragma: allowlist secret
                    name="첫 회장",
                    role="president",
                    status="active",
                    expires_at=future,
                    profile={},
                ),
                User(
                    email="second@example.com",
                    password_hash="unused",  # pragma: allowlist secret
                    name="둘째 회장",
                    role="president",
                    status="active",
                    expires_at=future,
                    profile={},
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_transfer_rolls_back_every_change_when_commit_fails(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    current = await _seed_user(
        factory, email="current@example.com", name="현재 회장", role="president"
    )
    target = await _seed_user(factory, email="target@example.com", name="차기 회장", role="staff")

    async with factory() as session:
        actor = await session.get(User, owner.id)
        assert actor is not None

        async def fail_commit() -> None:
            raise RuntimeError("synthetic commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="synthetic"):
            await transfer_president(
                session, actor=actor, to_user_id=target.id, note="rollback test"
            )

    async with factory() as session:
        assert (await session.get(User, current.id)).role == "president"  # type: ignore[union-attr]
        assert (await session.get(User, target.id)).role == "staff"  # type: ignore[union-attr]
        transfers = (await session.execute(select(PresidentTransfer))).scalars().all()
        assert transfers == []


@pytest.mark.asyncio
async def test_owner_can_appoint_and_replace_president_with_audit_history(
    api_harness: ApiHarness,
) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    first = await _seed_user(factory, email="first@example.com", name="첫 회장", role="staff")
    second = await _seed_user(factory, email="second@example.com", name="둘째 회장", role="staff")

    first_response = await client.post(
        "/admin/president/transfer",
        headers=_headers(owner),
        json={"to_user_id": str(first.id), "note": "최초 임명"},
    )
    assert first_response.status_code == 200
    assert first_response.json()["name"] == "첫 회장"

    second_response = await client.post(
        "/admin/president/transfer",
        headers=_headers(owner),
        json={"to_user_id": str(second.id), "note": "정기 인계"},
    )
    assert second_response.status_code == 200

    current = await client.get("/admin/president", headers=_headers(owner))
    assert current.status_code == 200
    assert current.json()["id"] == str(second.id)

    history = await client.get("/admin/president/transfers", headers=_headers(owner))
    assert history.status_code == 200
    rows = history.json()
    assert [row["note"] for row in rows] == ["정기 인계", "최초 임명"]
    assert rows[0]["from_user"]["name"] == "첫 회장"
    assert rows[0]["to_user"]["name"] == "둘째 회장"
    assert rows[0]["actor"]["name"] == "관리자"
    assert rows[1]["from_user"] is None


@pytest.mark.asyncio
async def test_president_self_transfer_immediately_loses_admin_access(
    api_harness: ApiHarness,
) -> None:
    client, factory, _ = api_harness
    current = await _seed_user(
        factory, email="current@example.com", name="현재 회장", role="president"
    )
    target = await _seed_user(factory, email="target@example.com", name="차기 회장", role="staff")
    old_headers = _headers(current)

    response = await client.post(
        "/admin/president/transfer",
        headers=old_headers,
        json={"to_user_id": str(target.id)},
    )
    assert response.status_code == 200

    denied = await client.get("/admin/president", headers=old_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "admin_required"


@pytest.mark.asyncio
async def test_staff_is_denied_and_owner_target_is_invalid(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    staff = await _seed_user(factory, email="staff@example.com", name="운영진", role="staff")

    denied = await client.get("/admin/president", headers=_headers(staff))
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "admin_required"

    invalid = await client.post(
        "/admin/president/transfer",
        headers=_headers(owner),
        json={"to_user_id": str(owner.id)},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "president_transfer_invalid"


@pytest.mark.asyncio
async def test_expired_or_inactive_target_is_invalid(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    expired = await _seed_user(
        factory,
        email="expired@example.com",
        name="만료 운영진",
        role="staff",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    inactive = await _seed_user(
        factory,
        email="inactive@example.com",
        name="중지 운영진",
        role="staff",
        status="suspended",
    )

    for target_id in (expired.id, inactive.id, uuid.uuid4()):
        response = await client.post(
            "/admin/president/transfer",
            headers=_headers(owner),
            json={"to_user_id": str(target_id)},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "president_transfer_invalid"
