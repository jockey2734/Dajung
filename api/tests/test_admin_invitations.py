"""Invitation administration API integration tests.

통과번호 관리 API 통합 테스트.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token, hash_password
from api.app.db.models import InvitationCode, User
from api.tests.conftest import ApiHarness


async def _seed_user(
    factory: async_sessionmaker[AsyncSession], *, email: str, role: str
) -> tuple[User, dict[str, str]]:
    user = User(
        email=email,
        password_hash=hash_password("admin-password"),  # pragma: allowlist secret
        name="합성 관리자",
        role=role,
        status="active",
        expires_at=None if role == "owner" else datetime.now(UTC) + timedelta(days=180),
        profile={},
    )
    async with factory() as session:
        session.add(user)
        await session.commit()
    token = create_access_token(user.id, user.email, user.role)
    return user, {"Authorization": f"Bearer {token}"}


async def test_staff_cannot_manage_invitations(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="staff@example.com", role="staff")

    response = await client.get("/admin/invitations", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_required"


async def test_created_code_is_returned_once_and_allows_signup(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")

    created = await client.post(
        "/admin/invitations",
        headers=headers,
        json={"note": "신규 운영진", "days": 7},
    )

    assert created.status_code == 201
    code = created.json()["code"]
    assert code
    assert created.text.count(code) == 1

    listed = await client.get("/admin/invitations", headers=headers)
    assert listed.status_code == 200
    assert code not in listed.text
    assert listed.json()[0]["status"] == "활성"

    signup = await client.post(
        "/auth/signup",
        json={
            "email": "new@example.com",
            "password": "signup-password",  # pragma: allowlist secret
            "name": "신규 운영진",
            "invitation_code": code,
        },
    )
    assert signup.status_code == 201


async def test_revoke_expires_without_deleting_invitation(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")
    created = await client.post("/admin/invitations", headers=headers, json={"days": 7})
    invitation_id = created.json()["id"]
    code = created.json()["code"]

    revoked = await client.post(f"/admin/invitations/{invitation_id}/revoke", headers=headers)

    assert revoked.status_code == 200
    assert revoked.json()["status"] == "만료"
    async with factory() as session:
        rows = (await session.execute(select(InvitationCode))).scalars().all()
        assert len(rows) == 1

    signup = await client.post(
        "/auth/signup",
        json={
            "email": "blocked@example.com",
            "password": "signup-password",  # pragma: allowlist secret
            "name": "차단 대상",
            "invitation_code": code,
        },
    )
    assert signup.status_code == 400


async def test_revoke_unknown_id_returns_404(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")

    response = await client.post(
        "/admin/invitations/11111111-1111-1111-1111-111111111111/revoke",
        headers=headers,
    )

    assert response.status_code == 404
