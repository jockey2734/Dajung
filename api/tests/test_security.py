"""Tests for password hashing, JWT lifecycle, and invitation-code hashing.

비밀번호 해싱, JWT 생명주기, 통과번호 해싱 테스트.
"""

from __future__ import annotations

import uuid

import jwt
import pytest

from api.app.core.config import settings
from api.app.core.security import (
    create_access_token,
    decode_access_token,
    hash_invitation_code,
    hash_password,
    verify_password,
)

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _auth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fast bcrypt and a fixed secret for every test in this module.

    이 모듈 전 테스트에 빠른 bcrypt cost와 고정 시크릿을 적용한다.
    """
    monkeypatch.setattr(settings, "bcrypt_rounds", 4)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")


class TestPassword:
    def test_roundtrip(self) -> None:
        hashed = hash_password("찻잔-secret-1")
        assert verify_password("찻잔-secret-1", hashed)

    def test_wrong_password_rejected(self) -> None:
        hashed = hash_password("right")
        assert not verify_password("wrong", hashed)

    def test_salt_makes_hashes_unique(self) -> None:
        assert hash_password("same") != hash_password("same")


class TestInvitationCode:
    def test_deterministic_hex(self) -> None:
        first = hash_invitation_code("DAJUNG-2026")
        assert first == hash_invitation_code("DAJUNG-2026")
        assert len(first) == 64
        assert first != hash_invitation_code("DAJUNG-2027")


class TestJwt:
    def test_roundtrip_claims(self) -> None:
        token = create_access_token(USER_ID, "unha@example.com", "owner")
        claims = decode_access_token(token)
        assert claims["sub"] == str(USER_ID)
        assert claims["email"] == "unha@example.com"
        assert claims["role"] == "owner"
        # 6-month absolute expiry (SECURITY.md §3) — no sliding renewal.
        # 6개월 absolute 만료 (SECURITY.md §3) — 슬라이딩 갱신 없음.
        assert claims["exp"] - claims["iat"] == settings.jwt_expires_days * 86400

    def test_expired_token_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "jwt_expires_days", -1)
        token = create_access_token(USER_ID, "unha@example.com", "staff")
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token(USER_ID, "unha@example.com", "staff")
        header, payload, signature = token.split(".")
        forged = f"{header}.{payload}x.{signature}"
        with pytest.raises(jwt.PyJWTError):
            decode_access_token(forged)

    def test_empty_secret_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "jwt_secret", "")
        with pytest.raises(RuntimeError, match="DAJUNG_JWT_SECRET"):
            create_access_token(USER_ID, "unha@example.com", "staff")
