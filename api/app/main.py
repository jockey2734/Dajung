"""FastAPI application factory.

FastAPI 애플리케이션 팩토리.

The factory pattern lets tests build a fresh app with clean state
(lockout counters, dependency overrides) per test.
팩토리 패턴 덕에 테스트가 매번 깨끗한 상태(잠금 카운터, 의존성
오버라이드)로 앱을 새로 만들 수 있다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from api.app.core.config import settings
from api.app.core.deps import SessionDep
from api.app.core.errors import ApiError
from api.app.core.lockout import LoginLockout
from api.app.core.ratelimit import limiter
from api.app.jobs.memory import create_memory_scheduler
from api.app.routes import (
    admin,
    admin_accounts,
    admin_docs,
    admin_invitations,
    admin_roster,
    auth,
    chat,
    feedback,
    files,
    pantry,
    privacy,
    sessions,
    uploads,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize optional serving-phase process resources.

    서빙 단계 프로세스 리소스를 초기화한다.
    """
    app.state.checkpointer = None
    app.state.memory_scheduler = create_memory_scheduler()
    app.state.memory_scheduler.start()
    try:
        if settings.database_url.startswith("postgresql"):
            checkpoint_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
            async with AsyncPostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
                await checkpointer.setup()
                app.state.checkpointer = checkpointer
                yield
        else:
            yield
    finally:
        app.state.memory_scheduler.shutdown(wait=False)
        app.state.memory_scheduler = None


def create_app() -> FastAPI:
    app = FastAPI(title="Dajung Ark API", version="0.1.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.state.lockout = LoginLockout(
        max_fails=settings.login_max_fails,
        window_s=settings.login_window_s,
        lock_s=settings.login_lock_s,
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        # Single renderer for the serving-plan §3 error envelope.
        # serving-plan §3 에러 포맷의 단일 렌더러.
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limited(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요.",
                }
            },
        )

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(admin_accounts.router)
    app.include_router(admin_docs.router)
    app.include_router(admin_invitations.router)
    app.include_router(admin_roster.router)
    app.include_router(chat.router)
    app.include_router(feedback.router)
    app.include_router(sessions.router)
    app.include_router(files.router)
    app.include_router(privacy.router)
    app.include_router(pantry.router)
    app.include_router(uploads.router)

    @app.get("/healthz")
    async def healthz(session: SessionDep) -> dict[str, str]:
        try:
            await session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:  # noqa: BLE001 — health probe must never raise
            db_status = "down"
        qdrant_status = await _probe_qdrant()
        ollama_status = await _probe_ollama()
        all_ok = db_status == qdrant_status == ollama_status == "ok"
        return {
            "status": "ok" if all_ok else "degraded",
            "db": db_status,
            "qdrant": qdrant_status,
            "ollama": ollama_status,
        }

    return app


async def _probe_qdrant() -> str:
    """Reachability probe — must never raise (ARCHITECTURE §10).

    연결 프로브 — 절대 예외를 던지지 않는다 (ARCHITECTURE §10).
    """
    from starlette.concurrency import run_in_threadpool

    from api.app.rag.qdrant_store import get_client

    try:
        await run_in_threadpool(get_client().get_collections)
        return "ok"
    except Exception:  # noqa: BLE001 — health probe must never raise
        return "down"


async def _probe_ollama() -> str:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=settings.health_probe_timeout_s) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
        return "ok"
    except Exception:  # noqa: BLE001 — health probe must never raise
        return "down"


app = create_app()
