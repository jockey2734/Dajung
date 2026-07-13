"""Admin account-management integration tests with synthetic users.

합성 사용자 기반 관리자 계정 관리 통합 테스트.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token, hash_password, verify_password
from api.app.db.models import User
from api.tests.conftest import ApiHarness


async def _seed_user(
    factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    name: str,
    role: str,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("initial-password"),  # pragma: allowlist secret
        name=name,
        role=role,
        status="active",
        expires_at=None if role == "owner" else datetime.now(UTC) + timedelta(days=180),
        profile={},
    )
    async with factory() as session:
        session.add(user)
        await session.commit()
    return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.email, user.role)
    return {"Authorization": f"Bearer {token}"}


async def test_admin_lists_account_fields(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    staff = await _seed_user(factory, email="staff@example.com", name="운영진", role="staff")

    response = await client.get("/admin/users", headers=_headers(owner))

    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()}
    assert rows[str(staff.id)].keys() == {
        "id",
        "name",
        "email",
        "title",
        "role",
        "status",
        "expires_at",
        "last_seen_at",
        "must_change_password",
    }


@pytest.mark.parametrize("path", ["patch", "reset"])
async def test_president_cannot_modify_owner(api_harness: ApiHarness, path: str) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    president = await _seed_user(
        factory, email="president@example.com", name="회장", role="president"
    )

    if path == "patch":
        response = await client.patch(
            f"/admin/users/{owner.id}",
            headers=_headers(president),
            json={"title": "수정 불가"},
        )
    else:
        response = await client.post(
            f"/admin/users/{owner.id}/password-reset", headers=_headers(president)
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_required"


async def test_owner_can_only_modify_own_owner_row(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    actor = await _seed_user(factory, email="owner1@example.com", name="관리자1", role="owner")
    other = await _seed_user(factory, email="owner2@example.com", name="관리자2", role="owner")

    response = await client.patch(
        f"/admin/users/{other.id}", headers=_headers(actor), json={"title": "수정 불가"}
    )

    assert response.status_code == 403


async def test_self_suspend_and_non_owner_null_expiry_are_rejected(
    api_harness: ApiHarness,
) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    staff = await _seed_user(factory, email="staff@example.com", name="운영진", role="staff")

    self_suspend = await client.patch(
        f"/admin/users/{owner.id}", headers=_headers(owner), json={"status": "suspended"}
    )
    null_expiry = await client.patch(
        f"/admin/users/{staff.id}", headers=_headers(owner), json={"expires_at": None}
    )

    assert self_suspend.status_code == 422
    assert null_expiry.status_code == 422


async def test_owner_can_clear_expiry_and_staff_fields_can_be_updated(
    api_harness: ApiHarness,
) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    staff = await _seed_user(factory, email="staff@example.com", name="운영진", role="staff")
    new_expiry = datetime.now(UTC) + timedelta(days=30)

    owner_set = await client.patch(
        f"/admin/users/{owner.id}",
        headers=_headers(owner),
        json={"expires_at": new_expiry.isoformat()},
    )
    assert owner_set.status_code == 200
    owner_clear = await client.patch(
        f"/admin/users/{owner.id}", headers=_headers(owner), json={"expires_at": None}
    )
    updated = await client.patch(
        f"/admin/users/{staff.id}",
        headers=_headers(owner),
        json={"title": None, "status": "suspended", "expires_at": new_expiry.isoformat()},
    )

    assert owner_clear.status_code == 200
    assert owner_clear.json()["expires_at"] is None
    assert updated.status_code == 200
    assert updated.json()["status"] == "suspended"
    assert updated.json()["title"] is None


async def test_password_reset_requires_change_then_user_clears_flag(
    api_harness: ApiHarness,
) -> None:
    client, factory, _ = api_harness
    owner = await _seed_user(factory, email="owner@example.com", name="관리자", role="owner")
    staff = await _seed_user(factory, email="staff@example.com", name="운영진", role="staff")

    reset = await client.post(f"/admin/users/{staff.id}/password-reset", headers=_headers(owner))
    assert reset.status_code == 200
    temporary = reset.json()["temporary_password"]
    assert temporary
    assert reset.text.count(temporary) == 1

    async with factory() as session:
        stored = await session.get(User, staff.id)
        assert stored is not None
        assert stored.must_change_password is True
        assert stored.password_hash != temporary
        assert verify_password(temporary, stored.password_hash)

    signin = await client.post(
        "/auth/signin",
        json={"email": staff.email, "password": temporary},  # pragma: allowlist secret
    )
    assert signin.status_code == 200
    assert signin.json()["user"]["must_change_password"] is True
    token = signin.json()["access_token"]

    changed = await client.patch(
        "/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": temporary,
            "new_password": "replacement-password",  # pragma: allowlist secret
        },
    )
    assert changed.status_code == 204

    signed_in_again = await client.post(
        "/auth/signin",
        json={
            "email": staff.email,
            "password": "replacement-password",  # pragma: allowlist secret
        },
    )
    assert signed_in_again.status_code == 200
    assert signed_in_again.json()["user"]["must_change_password"] is False


async def test_password_change_rejects_wrong_current_password(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    staff = await _seed_user(factory, email="staff@example.com", name="운영진", role="staff")

    response = await client.patch(
        "/auth/password",
        headers=_headers(staff),
        json={
            "current_password": "wrong-password",  # pragma: allowlist secret
            "new_password": "replacement-password",  # pragma: allowlist secret
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_credentials"
