"""Request-scoped auth dependencies.

요청 단위 인증 의존성.

FastAPI verifies signature + expiry from the JWT, then confirms the user
still exists and is active in the DB — forced logout works via status.
FastAPI가 JWT 서명·만료를 검증한 뒤, DB에서 사용자가 존재하고 활성인지
확인한다 — status로 강제 로그아웃이 가능하다 (serving-plan §2).
"""

from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.errors import ApiError
from api.app.core.security import decode_access_token
from api.app.db.base import get_session
from api.app.db.models import User

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
) -> User:
    """Resolve the Bearer token to an active User or raise 401.

    Bearer 토큰을 활성 User로 해석하고, 실패 시 401을 던진다.
    """
    if credentials is None:
        raise ApiError(401, "token_invalid", "인증 토큰이 없습니다.")
    try:
        claims = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(
            401, "token_expired", "로그인이 만료되었습니다. 다시 로그인해 주세요."
        ) from exc
    except jwt.PyJWTError as exc:
        raise ApiError(401, "token_invalid", "유효하지 않은 인증 토큰입니다.") from exc

    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None or user.status != "active":
        raise ApiError(401, "token_invalid", "사용할 수 없는 계정입니다.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
