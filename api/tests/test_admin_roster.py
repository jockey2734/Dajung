"""Semester roster API and account-term integration tests.

학기별 명단 API와 계정 임기 연동 테스트.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.account_term import to_utc
from api.app.core.security import create_access_token, hash_password
from api.app.db.models import User
from api.app.routes import admin_roster as roster_routes
from api.tests.conftest import ApiHarness

FIXED_NOW = datetime(2026, 7, 13, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fixed_roster_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(roster_routes, "roster_now", lambda: FIXED_NOW)


async def _seed_user(
    factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    role: str,
    expires_at: datetime | None = None,
) -> tuple[User, dict[str, str]]:
    if expires_at is None and role != "owner":
        expires_at = FIXED_NOW + timedelta(days=30)
    user = User(
        email=email,
        password_hash=hash_password("roster-password"),  # pragma: allowlist secret
        name=email.split("@", maxsplit=1)[0],
        role=role,
        status="active",
        expires_at=expires_at,
        profile={},
    )
    async with factory() as session:
        session.add(user)
        await session.commit()
    token = create_access_token(user.id, user.email, user.role)
    return user, {"Authorization": f"Bearer {token}"}


async def test_roster_crud_and_semester_filter(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")

    first = await client.post(
        "/admin/roster",
        headers=headers,
        json={
            "semester": "2026-1",
            "department": "기획부",
            "member_name": "합성 회원",
            "position": "부장",
        },
    )
    assert first.status_code == 201
    roster_id = first.json()["id"]

    await client.post(
        "/admin/roster",
        headers=headers,
        json={"semester": "2025-2", "department": "총무부", "member_name": "과거 회원"},
    )
    listed = await client.get("/admin/roster?semester=2026-1", headers=headers)
    assert listed.status_code == 200
    assert [row["member_name"] for row in listed.json()] == ["합성 회원"]

    updated = await client.patch(
        f"/admin/roster/{roster_id}",
        headers=headers,
        json={"department": "집행부", "position": None},
    )
    assert updated.status_code == 200
    assert updated.json()["department"] == "집행부"
    assert updated.json()["position"] is None

    deleted = await client.delete(f"/admin/roster/{roster_id}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/admin/roster?semester=2026-1", headers=headers)).json() == []


async def test_duplicate_member_and_unknown_user_are_rejected(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")
    body = {"semester": "2026-1", "department": "기획부", "member_name": "중복 회원"}
    assert (await client.post("/admin/roster", headers=headers, json=body)).status_code == 201

    duplicate = await client.post("/admin/roster", headers=headers, json=body)
    missing = await client.post(
        "/admin/roster",
        headers=headers,
        json={
            "semester": "2026-1",
            "department": "기획부",
            "member_name": "미연결 회원",
            "user_id": "11111111-1111-1111-1111-111111111111",
        },
    )

    assert duplicate.status_code == 409
    assert missing.status_code == 422


async def test_current_semester_extends_to_october_first(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")
    staff, _ = await _seed_user(factory, email="staff@example.com", role="staff")

    response = await client.post(
        "/admin/roster",
        headers=headers,
        json={
            "semester": "2026-1",
            "department": "기획부",
            "member_name": "현재 회원",
            "user_id": str(staff.id),
        },
    )

    assert response.status_code == 201
    async with factory() as session:
        stored = await session.get(User, staff.id)
        assert stored is not None and stored.expires_at is not None
        assert to_utc(stored.expires_at) == datetime(2026, 9, 30, 15, tzinfo=UTC)


async def test_future_roster_never_shortens_existing_term(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")
    existing = datetime(2027, 5, 1, tzinfo=UTC)
    staff, _ = await _seed_user(
        factory, email="staff@example.com", role="staff", expires_at=existing
    )

    response = await client.post(
        "/admin/roster",
        headers=headers,
        json={
            "semester": "2026-2",
            "department": "총무부",
            "member_name": "미래 회원",
            "user_id": str(staff.id),
        },
    )

    assert response.status_code == 201
    async with factory() as session:
        stored = await session.get(User, staff.id)
        assert stored is not None and stored.expires_at is not None
        assert to_utc(stored.expires_at) == existing


async def test_past_roster_and_owner_link_do_not_change_terms(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    owner, headers = await _seed_user(factory, email="owner@example.com", role="owner")
    existing = datetime(2026, 8, 1, tzinfo=UTC)
    staff, _ = await _seed_user(
        factory, email="staff@example.com", role="staff", expires_at=existing
    )

    for member_name, user_id in (("과거 회원", staff.id), ("owner 회원", owner.id)):
        semester = "2025-2" if user_id == staff.id else "2026-2"
        response = await client.post(
            "/admin/roster",
            headers=headers,
            json={
                "semester": semester,
                "department": "집행부",
                "member_name": member_name,
                "user_id": str(user_id),
            },
        )
        assert response.status_code == 201

    async with factory() as session:
        stored_staff = await session.get(User, staff.id)
        stored_owner = await session.get(User, owner.id)
        assert stored_staff is not None and stored_staff.expires_at is not None
        assert to_utc(stored_staff.expires_at) == existing
        assert stored_owner is not None and stored_owner.expires_at is None


async def test_link_added_by_patch_extends_term_and_delete_does_not_reverse_it(
    api_harness: ApiHarness,
) -> None:
    client, factory, _ = api_harness
    _, headers = await _seed_user(factory, email="owner@example.com", role="owner")
    staff, _ = await _seed_user(factory, email="staff@example.com", role="staff")
    created = await client.post(
        "/admin/roster",
        headers=headers,
        json={"semester": "2026-2", "department": "홍보부", "member_name": "연결 회원"},
    )
    roster_id = created.json()["id"]

    linked = await client.patch(
        f"/admin/roster/{roster_id}", headers=headers, json={"user_id": str(staff.id)}
    )
    assert linked.status_code == 200
    async with factory() as session:
        stored = await session.get(User, staff.id)
        assert stored is not None and stored.expires_at is not None
        extended = to_utc(stored.expires_at)
    assert extended == datetime(2027, 3, 31, 15, tzinfo=UTC)

    assert (await client.delete(f"/admin/roster/{roster_id}", headers=headers)).status_code == 204
    async with factory() as session:
        stored = await session.get(User, staff.id)
        assert stored is not None and stored.expires_at is not None
        assert to_utc(stored.expires_at) == extended
