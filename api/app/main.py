"""FastAPI application factory.

FastAPI 애플리케이션 팩토리.

The factory pattern lets tests build a fresh app with clean state
(lockout counters, dependency overrides) per test.
팩토리 패턴 덕에 테스트가 매번 깨끗한 상태(잠금 카운터, 의존성
오버라이드)로 앱을 새로 만들 수 있다.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from api.app.core.config import settings
from api.app.core.deps import SessionDep
from api.app.core.errors import ApiError
from api.app.core.lockout import LoginLockout
from api.app.core.ratelimit import limiter
from api.app.routes import auth


def create_app() -> FastAPI:
    app = FastAPI(title="Dajung Ark API", version="0.1.0")
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

    @app.get("/healthz")
    async def healthz(session: SessionDep) -> dict[str, str]:
        # Qdrant/Ollama probes arrive with the serving branch (cx-api-serve).
        # Qdrant/Ollama 프로브는 서빙 브랜치(cx-api-serve)에서 붙는다.
        try:
            await session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:  # noqa: BLE001 — health probe must never raise
            db_status = "down"
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "db": db_status,
            "qdrant": "not_checked",
            "ollama": "not_checked",
        }

    return app


app = create_app()
