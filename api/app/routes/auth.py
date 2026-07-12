"""Signup, signin, and current-user endpoints (serving-plan §1, §3).

가입·로그인·현재 사용자 엔드포인트 (serving-plan §1, §3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, Request
from sqlalchemy import select

from api.app.core.account_term import (
    ACCOUNT_EXPIRED_MESSAGE,
    ACCOUNT_TERM_MONTHS,
    add_months,
    is_account_expired,
    to_utc,
)
from api.app.core.deps import CurrentUser, SessionDep
from api.app.core.errors import ApiError
from api.app.core.lockout import LoginLockout
from api.app.core.ratelimit import ip_limit, limiter
from api.app.core.security import (
    create_access_token,
    hash_invitation_code,
    hash_password,
    verify_password,
)
from api.app.db.models import InvitationCode, User
from api.app.schemas.auth import (
    SigninRequest,
    SigninResponse,
    SignupRequest,
    SignupResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Constant-cost hash used when the email does not exist.

    이메일이 없을 때도 같은 비용을 쓰기 위한 더미 해시.
    Without it, a fast "no such user" reply lets attackers enumerate emails
    by timing. 없으면 빠른 응답 시간 차이로 이메일 존재 여부가 노출된다.
    """
    return hash_password("dajung-dummy-password")


@router.post("/signup", status_code=201)
@limiter.limit(ip_limit)
async def signup(request: Request, body: SignupRequest, session: SessionDep) -> SignupResponse:
    now = datetime.now(UTC)
    code_hash = hash_invitation_code(body.invitation_code)
    invitation = (
        await session.execute(select(InvitationCode).where(InvitationCode.code_hash == code_hash))
    ).scalar_one_or_none()
    if invitation is None or invitation.used_at is not None or to_utc(invitation.expires_at) <= now:
        raise ApiError(400, "invalid_code", "유효하지 않은 통과번호입니다.")

    email = body.email.lower()
    existing = (
        await session.execute(select(User.id).where(User.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        raise ApiError(409, "email_exists", "이미 가입된 이메일입니다.")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name,
        role="staff",
        status="active",
        expires_at=add_months(now, ACCOUNT_TERM_MONTHS),
        profile={},
    )
    session.add(user)
    # Flush assigns user.id before marking the code used in the same transaction.
    # 같은 트랜잭션에서 코드 사용 처리 전에 flush로 user.id를 확보한다.
    await session.flush()
    invitation.used_at = now
    invitation.used_by = user.id
    await session.commit()
    return SignupResponse(user_id=user.id)


@router.post("/signin")
@limiter.limit(ip_limit)
async def signin(request: Request, body: SigninRequest, session: SessionDep) -> SigninResponse:
    lockout: LoginLockout = request.app.state.lockout
    email = body.email.lower()
    if lockout.is_locked(email):
        raise ApiError(
            429, "locked_out", "로그인 시도가 너무 많습니다. 1시간 후 다시 시도해 주세요."
        )

    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    password_ok = (
        verify_password(body.password, user.password_hash)
        if user is not None
        else verify_password(body.password, _dummy_hash())
    )
    if user is None or user.status != "active" or not password_ok:
        lockout.record_failure(email)
        raise ApiError(401, "bad_credentials", "이메일 또는 비밀번호가 올바르지 않습니다.")
    if is_account_expired(user.role, user.expires_at):
        raise ApiError(401, "account_expired", ACCOUNT_EXPIRED_MESSAGE)

    lockout.clear(email)
    user.last_seen_at = datetime.now(UTC)
    await session.commit()
    token = create_access_token(user.id, user.email, user.role)
    return SigninResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me")
async def me(current: CurrentUser) -> UserOut:
    """Session probe for the BFF — validates the token, returns the user.

    BFF용 세션 확인 — 토큰을 검증하고 사용자를 돌려준다.
    """
    return UserOut.model_validate(current)
