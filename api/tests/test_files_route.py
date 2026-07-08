"""Files listing route — qdrant scroll mocked.

파일 목록 라우트 — qdrant scroll 모킹.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.app.core.security import create_access_token, hash_password
from api.app.db.models import User
from api.app.routes import files as files_mod
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


async def test_files_aggregated_per_doc(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = api_harness

    def fake_scan() -> list[dict[str, object]]:
        return [
            {
                "doc_id": "d1",
                "source_file": "예산안.xlsx",
                "doc_type": "budget",
                "semester": "2025-1",
                "restricted": False,
                "chunk_count": 3,
            }
        ]

    monkeypatch.setattr(files_mod, "_scan_files", fake_scan)
    resp = await client.get("/files", headers=await _headers(factory))
    assert resp.status_code == 200
    files = resp.json()["files"]
    assert files[0]["source_file"] == "예산안.xlsx"
    assert files[0]["chunk_count"] == 3


async def test_files_qdrant_down_503(
    api_harness: ApiHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = api_harness

    def boom() -> list[dict[str, object]]:
        raise ConnectionError("qdrant down")

    monkeypatch.setattr(files_mod, "_scan_files", boom)
    resp = await client.get("/files", headers=await _headers(factory))
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "qdrant_down"


async def test_files_requires_auth(api_harness: ApiHarness) -> None:
    client, *_ = api_harness
    assert (await client.get("/files")).status_code == 401
