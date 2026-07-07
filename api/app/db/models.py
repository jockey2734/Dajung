"""ORM models — users and invitation codes.

ORM 모델 — 사용자와 통과번호.

Schema source of truth: webapp-plan.md §5.
스키마 단일 기준: webapp-plan.md §5.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.app.db.base import Base


class User(Base):
    """Staff account — ``role`` drives authz, ``title`` is display-only.

    운영진 계정 — ``role``이 권한을 결정하고 ``title``은 표시 전용이다.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'staff')", name="ck_users_role"),
        CheckConstraint("status IN ('active', 'suspended', 'deleted')", name="ck_users_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(10), default="staff")
    # Job title (회장, 총무부장, …) — rotates every semester, never checked by code.
    # 직책(회장, 총무부장 등) — 학기마다 바뀌며 코드가 검사하지 않는다.
    title: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10), default="active")
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InvitationCode(Base):
    """Single-use signup gate code issued by the owner (SECURITY.md §3).

    owner가 발급하는 단일 사용 가입 게이트 코드 (SECURITY.md §3).

    Stored as a SHA-256 hash — the plaintext is shown once at issue time
    and delivered via KakaoTalk/SMS only, never email.
    SHA-256 해시로 저장 — 평문은 발급 순간 한 번만 표시되며
    카카오톡·문자로만 전달한다 (이메일 금지).
    """

    __tablename__ = "invitation_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Free-text memo: who this code is meant for.
    # 누구에게 줄 코드인지 적는 자유 메모.
    note: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
