"""Privacy-consent route tests.

개인정보 동의 라우트 테스트.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token, hash_password
from api.app.db.models import User
from api.app.routes.privacy import PRIVACY_POLICY_VERSION
from api.tests.conftest import ApiHarness


async def _headers(factory: async_sessionmaker[AsyncSession]) -> dict[str, str]:
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
    return {"Authorization": f"Bearer {create_access_token(user.id, user.email, user.role)}"}


async def test_privacy_consent_round_trip(api_harness: ApiHarness) -> None:
    client, factory, _ = api_harness
    headers = await _headers(factory)

    resp = await client.get("/privacy-consent", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"consented": False, "version": None}

    resp = await client.post(
        "/privacy-consent",
        json={"version": PRIVACY_POLICY_VERSION},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"consented": True, "version": PRIVACY_POLICY_VERSION}

    resp = await client.get("/privacy-consent", headers=headers)
    assert resp.json() == {"consented": True, "version": PRIVACY_POLICY_VERSION}


async def test_privacy_consent_requires_auth(api_harness: ApiHarness) -> None:
    client, *_ = api_harness
    assert (await client.get("/privacy-consent")).status_code == 401
