"""Pantry CRUD routes tests.

찻장 CRUD 라우터 테스트.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token, hash_password
from api.app.db.models import User
from api.tests.conftest import ApiHarness


async def _headers_and_user(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[dict[str, str], str]:
    async with factory() as session:
        user = User(
            email="staff@test.local",
            password_hash=hash_password("pw12345678"),
            name="스태프",
            role="staff",
            status="active",
            profile={},
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(user.id, user.email, user.role)}"}, str(
        user.id
    )


async def test_pantry_crud_round_trip(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    headers, user_id = await _headers_and_user(factory)

    # 1. GET (empty)
    resp = await client.get("/pantry", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["coffee_alert"]["alert"] is True
    assert data["coffee_alert"]["total_estimated_g"] == 0

    # 2. POST (new coffee item)
    resp = await client.post(
        "/pantry",
        json={
            "name": "Ethiopia Yirgacheffe",
            "kind": "coffee",
            "remaining_pct": 50,
            "capacity_g": 500,
            "note": "Acidic",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    created_item = resp.json()["item"]
    item_id = created_item["id"]
    assert created_item["name"] == "Ethiopia Yirgacheffe"
    assert created_item["estimated_g"] == 250
    assert created_item["updated_by"]["id"] == user_id

    # 3. GET (should contain 1 item)
    resp = await client.get("/pantry", headers=headers)
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["coffee_alert"]["alert"] is True
    assert data["coffee_alert"]["total_estimated_g"] == 250

    # 4. PATCH (update remaining_pct to 100)
    resp = await client.patch(
        f"/pantry/{item_id}",
        json={"remaining_pct": 100},
        headers=headers,
    )
    assert resp.status_code == 200
    updated_item = resp.json()["item"]
    assert updated_item["remaining_pct"] == 100
    assert updated_item["estimated_g"] == 500
    assert resp.json()["coffee_alert"]["alert"] is False
    assert resp.json()["coffee_alert"]["total_estimated_g"] == 500

    # 5. GET (should reflect update)
    resp = await client.get("/pantry", headers=headers)
    data = resp.json()
    assert data["items"][0]["remaining_pct"] == 100
    assert data["coffee_alert"]["alert"] is False

    # 6. DELETE
    resp = await client.delete(f"/pantry/{item_id}", headers=headers)
    assert resp.status_code == 204

    # 7. GET (empty again)
    resp = await client.get("/pantry", headers=headers)
    data = resp.json()
    assert data["items"] == []
    assert data["coffee_alert"]["alert"] is True


async def test_pantry_banner_calculation(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    headers, _ = await _headers_and_user(factory)

    # 1. Add tea (should not affect coffee banner)
    await client.post(
        "/pantry",
        json={
            "name": "Jasmine Tea",
            "kind": "tea",
            "remaining_pct": 100,
        },
        headers=headers,
    )

    # 2. Add coffee with NULL capacity_g (should not affect banner)
    await client.post(
        "/pantry",
        json={
            "name": "Unknown Coffee",
            "kind": "coffee",
            "remaining_pct": 50,
            "capacity_g": None,
        },
        headers=headers,
    )

    resp = await client.get("/pantry", headers=headers)
    data = resp.json()
    assert data["coffee_alert"]["total_estimated_g"] == 0

    # 3. Add valid coffee
    await client.post(
        "/pantry",
        json={
            "name": "Espresso Blend",
            "kind": "coffee",
            "remaining_pct": 25,
            "capacity_g": 1000,
        },
        headers=headers,
    )

    resp = await client.get("/pantry", headers=headers)
    data = resp.json()
    # 1000g * 25% = 250g
    assert data["coffee_alert"]["total_estimated_g"] == 250
    assert data["coffee_alert"]["alert"] is True

    # 4. Add another valid coffee
    await client.post(
        "/pantry",
        json={
            "name": "Decaf Blend",
            "kind": "coffee",
            "remaining_pct": 75,
            "capacity_g": 500,
        },
        headers=headers,
    )

    resp = await client.get("/pantry", headers=headers)
    data = resp.json()
    # 250g + (500g * 75%) = 250 + 375 = 625g
    assert data["coffee_alert"]["total_estimated_g"] == 625
    assert data["coffee_alert"]["alert"] is False


async def test_pantry_requires_auth(api_harness: ApiHarness) -> None:
    client, *_ = api_harness
    assert (await client.get("/pantry")).status_code == 401
    assert (await client.post("/pantry", json={})).status_code == 401
    assert (await client.patch("/pantry/123", json={})).status_code == 401
    assert (await client.delete("/pantry/123")).status_code == 401
