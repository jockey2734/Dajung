"""Password hashing, JWT issuance/verification, invitation-code hashing.

비밀번호 해싱, JWT 발급·검증, 통과번호 해싱.

Pure functions only — no I/O, no framework imports, so each is testable
in isolation. Claim shape follows serving-plan.md §2.
순수 함수만 — I/O·프레임워크 임포트가 없어 단독 테스트가 가능하다.
클레임 형태는 serving-plan.md §2를 따른다.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from api.app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (cost from settings, default 12).

    비밀번호를 bcrypt로 해싱한다 (cost는 settings, 기본 12).
    """
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash.

    평문 비밀번호를 저장된 bcrypt 해시와 대조한다.
    """
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def hash_invitation_code(code: str) -> str:
    """Deterministic SHA-256 hex digest for invitation-code lookup.

    통과번호 조회용 결정적 SHA-256 hex 다이제스트.
    """
    return hashlib.sha256(code.encode()).hexdigest()


def create_access_token(user_id: uuid.UUID, email: str, role: str) -> str:
    """Issue an HS256 JWT with a 6-month absolute expiry.

    6개월 absolute 만료의 HS256 JWT를 발급한다.
    """
    if not settings.jwt_secret:
        # Refuse to sign with an empty secret — a misconfigured .env must fail loudly.
        # 빈 시크릿으로는 서명하지 않는다 — .env 설정 누락은 시끄럽게 실패해야 한다.
        raise RuntimeError("DAJUNG_JWT_SECRET is not set")
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.jwt_expires_days)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify signature and expiry; return claims.

    서명과 만료를 검증하고 클레임을 반환한다.

    Raises ``jwt.PyJWTError`` subclasses on invalid or expired tokens —
    callers map them to 401 ``token_expired`` / ``token_invalid``.
    무효·만료 토큰이면 ``jwt.PyJWTError`` 하위 예외를 던진다 —
    호출부가 401 ``token_expired`` / ``token_invalid``로 매핑한다.
    """
    if not settings.jwt_secret:
        raise RuntimeError("DAJUNG_JWT_SECRET is not set")
    claims: dict[str, Any] = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    return claims
