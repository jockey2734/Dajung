"""Async database engine and request-scoped session dependency.

비동기 데이터베이스 엔진과 요청 단위 세션 의존성.

One engine (connection pool) per process; each request gets its own
short-lived session via the ``get_session`` FastAPI dependency.
프로세스당 엔진(커넥션 풀) 하나. 각 요청은 ``get_session`` FastAPI
의존성으로 자기만의 짧은 세션을 받는다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model.

    모든 ORM 모델이 공유하는 선언적 베이스.
    """


# pool_pre_ping revalidates pooled connections, surviving Postgres restarts.
# pool_pre_ping은 풀의 커넥션을 재검증해 Postgres 재시작에도 살아남게 한다.
engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)

# expire_on_commit=False keeps loaded attributes readable after commit.
# expire_on_commit=False는 커밋 후에도 로드된 속성을 읽을 수 있게 한다.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one session per request; closes automatically afterwards.

    요청당 세션 하나를 내어주고, 끝나면 자동으로 닫는다.
    """
    async with SessionLocal() as session:
        yield session
