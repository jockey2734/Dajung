"""Shared synthetic fixtures (Dajung.md §9). Never real club data.

공용 합성 픽스처 (Dajung.md §9). 실자료 사용 금지.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ApiHarness = tuple[AsyncClient, "async_sessionmaker[AsyncSession]", FastAPI]


@pytest.fixture
async def api_harness(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ApiHarness]:
    """App + in-memory SQLite + client — shared by serving-route tests.

    앱 + 인메모리 SQLite + 클라이언트 — 서빙 라우트 테스트 공용.
    """
    from api.app.core.config import settings
    from api.app.core.ratelimit import limiter
    from api.app.db.base import Base, get_session
    from api.app.main import create_app

    monkeypatch.setattr(settings, "bcrypt_rounds", 4)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")

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


@pytest.fixture
def fake_user_staff() -> dict[str, str]:
    return {"id": "user-staff-1", "email": "staff@test.local", "role": "staff"}


@pytest.fixture
def fake_user_owner() -> dict[str, str]:
    return {"id": "user-owner-1", "email": "owner@test.local", "role": "owner"}


@pytest.fixture
def fake_chunks() -> list[dict[str, Any]]:
    """Six candidate chunks — a mix of open and restricted payloads.

    공개/제한 payload가 섞인 후보 청크 6개.
    """

    def chunk(i: int, restricted: bool, allowed: list[str]) -> dict[str, Any]:
        return {
            "payload": {
                "doc_id": f"doc-{i}",
                "source_file": f"file_{i}.md",
                "doc_type": "handover" if i % 2 else "tea_knowledge",
                "category": "테스트",
                "semester": "2025-1",
                "sensitivity": "high" if restricted else "low",
                "chunk_index": 0,
                "total_chunks": 1,
                "locator": f"sec:{i}",
                "restricted": restricted,
                "allowed_users": allowed,
                "text": f"synthetic chunk body {i}",
                "context_header": f"[문서: file_{i}.md | sec:{i} | 분류: 테스트]",
            },
            "score": 1.0 - i * 0.1,
        }

    return [
        chunk(0, False, []),
        chunk(1, False, []),
        chunk(2, True, []),
        chunk(3, True, ["user-staff-1"]),
        chunk(4, True, ["someone-else"]),
        chunk(5, False, []),
    ]


@pytest.fixture
def fake_reranked() -> list[dict[str, Any]]:
    """Three reranked entries with descending scores 0.9 / 0.6 / 0.4.

    점수 0.9 / 0.6 / 0.4 내림차순 리랭크 결과 3개.
    """
    out: list[dict[str, Any]] = []
    for i, score in enumerate([0.9, 0.6, 0.4]):
        out.append(
            {
                "payload": {
                    "source_file": f"ranked_{i}.md",
                    "locator": f"p.{i + 1}",
                    "category": "테스트",
                    "semester": "2025-1",
                    "text": f"ranked body {i}",
                    "context_header": f"[문서: ranked_{i}.md]",
                },
                "rerank_score": score,
            }
        )
    return out


@pytest.fixture
def tmp_docs(tmp_path: Path) -> Path:
    """Synthetic md/txt documents in a temp directory.

    임시 디렉토리에 합성 md/txt 문서를 만든다.
    """
    (tmp_path / "guide.md").write_text(
        "# 개완 사용법\n\n## 준비\n\n물을 끓인다.\n\n## 우리기\n\n30초 우린다.\n",
        encoding="utf-8",
    )
    (tmp_path / "note.txt").write_text("차 보관은 밀폐용기에 한다.\n", encoding="utf-8")
    return tmp_path
