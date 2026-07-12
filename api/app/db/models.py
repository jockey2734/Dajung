"""ORM models — users and invitation codes.

ORM 모델 — 사용자와 통과번호.

Schema source of truth: webapp-plan.md §5.
스키마 단일 기준: webapp-plan.md §5.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.app.db.base import Base

# Portable JSON: JSONB on Postgres, plain JSON elsewhere (SQLite in tests).
# 이식 가능한 JSON: Postgres에선 JSONB, 그 외(테스트 SQLite)는 일반 JSON.
PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    """Staff account — ``role`` drives authz, ``title`` is display-only.

    운영진 계정 — ``role``이 권한을 결정하고 ``title``은 표시 전용이다.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'president', 'staff')", name="ck_users_role"),
        CheckConstraint("status IN ('active', 'suspended', 'deleted')", name="ck_users_status"),
        Index(
            "uq_users_single_president",
            "role",
            unique=True,
            postgresql_where=text("role = 'president'"),
            sqlite_where=text("role = 'president'"),
        ),
    )

    # Client-side uuid4 — works on SQLite too; migration adds gen_random_uuid() as belt.
    # 클라이언트 측 uuid4 — SQLite에서도 동작. 마이그레이션이 gen_random_uuid()를 보강한다.
    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(10), default="staff")
    # Job title (회장, 총무부장, …) — rotates every semester, never checked by code.
    # 직책(회장, 총무부장 등) — 학기마다 바뀌며 코드가 검사하지 않는다.
    title: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10), default="active")
    profile: Mapped[dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    # NULL is reserved for the owner, whose account has no operational term.
    # NULL은 운영 임기가 없는 owner에게만 사용한다.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PresidentTransfer(Base):
    """Permanent audit record for president appointments and transfers.

    회장 최초 임명·권한 이양을 영구 보존하는 감사 기록.
    """

    __tablename__ = "president_transfers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    from_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StaffSemester(Base):
    """Named executive roster row for one academic semester.

    한 학기 집행부 명단의 이름 기반 행.
    """

    __tablename__ = "staff_semesters"
    __table_args__ = (
        UniqueConstraint("semester", "member_name", name="uq_staff_semesters_semester_member"),
        CheckConstraint(
            "semester ~ '^[0-9]{4}-[12]$'",
            name="ck_staff_semesters_semester_postgresql",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "length(semester) = 6 AND semester GLOB '[0-9][0-9][0-9][0-9]-[12]'",
            name="ck_staff_semesters_semester_sqlite",
        ).ddl_if(dialect="sqlite"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    semester: Mapped[str] = mapped_column(String(7))
    department: Mapped[str] = mapped_column(String(30))
    member_name: Mapped[str] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(30))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    """One conversation thread — sidebar unit, LangGraph thread_id source.

    대화 스레드 1개 — 사이드바 단위이자 LangGraph thread_id의 원천.
    Schema: webapp-plan §5 (2026-07-07 확정).
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived', 'deleted')", name="ck_chat_sessions_status"
        ),
        Index("ix_chat_sessions_user_recent", "user_id", "last_message_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(10), default="active")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Counters updated in the same transaction as message inserts (no drift).
    # 카운터는 메시지 insert와 같은 트랜잭션에서 갱신한다 (드리프트 방지).
    message_count: Mapped[int] = mapped_column(Integer(), default=0)
    attachment_count: Mapped[int] = mapped_column(Integer(), default=0)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", PortableJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Message(Base):
    """One turn in a session. content is PII-masked at write time
    (SECURITY.md §8 — single storage, no separate chat_logs).

    세션의 턴 1개. content는 기록 시점에 PII 마스킹된다
    (SECURITY.md §8 — 단일 저장, 별도 chat_logs 없음).
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        CheckConstraint(
            "status IN ('completed', 'streaming', 'failed', 'deleted')",
            name="ck_messages_status",
        ),
        UniqueConstraint("session_id", "sequence_no", name="uq_messages_session_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    # NULL for assistant/system turns (webapp-plan §5).
    # assistant/system 턴은 NULL (webapp-plan §5).
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(20), default="markdown")
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id"))
    sequence_no: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(10), default="completed")
    error_code: Mapped[str | None] = mapped_column(String(30))
    # route / citations / model_used live here (webapp-plan §5).
    # route / citations / model_used는 여기에 담는다 (webapp-plan §5).
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", PortableJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Attachment(Base):
    """Conversation-scoped uploaded file and parsed text cache.

    대화 첨부 파일과 파싱 텍스트 캐시.
    """

    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('pending', 'parsed', 'failed')", name="ck_attachments_parse_status"
        ),
        Index("ix_attachments_user_id", "user_id"),
        Index("ix_attachments_sha256", "sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    # Nullable until the user sends a chat turn with the attachment.
    # 첨부를 포함해 채팅을 보내기 전까지는 NULL일 수 있다.
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chat_sessions.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(255))
    byte_size: Mapped[int] = mapped_column(Integer())
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(Text)
    parsed_text: Mapped[str] = mapped_column(Text, default="")
    parsed_chars: Mapped[int] = mapped_column(Integer(), default=0)
    parse_status: Mapped[str] = mapped_column(String(10), default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text)
    promoted_doc_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelRun(Base):
    """Metadata for one AI call, without raw prompts/responses (ADR-009).

    AI 호출 1회의 메타데이터. 원문 프롬프트/응답은 저장하지 않는다 (ADR-009).
    """

    __tablename__ = "model_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id"))
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"))
    model_provider: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    output_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    total_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer())
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    finish_reason: Mapped[str | None] = mapped_column(String(50))
    params: Mapped[dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetrievalEvent(Base):
    """Search telemetry for eval and citation-quality review.

    eval과 인용 품질 점검을 위한 검색 이벤트 기록.
    """

    __tablename__ = "retrieval_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id"))
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_runs.id"))
    query_text: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    top_k: Mapped[int] = mapped_column(Integer())
    chunks: Mapped[list[dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    latency_ms: Mapped[int | None] = mapped_column(Integer())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    """Thumbs up/down feedback for an assistant message.

    assistant 메시지에 대한 좋아요/싫어요 피드백.
    """

    __tablename__ = "feedbacks"
    __table_args__ = (
        CheckConstraint("rating IN (-1, 1)", name="ck_feedbacks_rating"),
        UniqueConstraint("message_id", "user_id", name="uq_feedbacks_message_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(SmallInteger())
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrivacyConsent(Base):
    """Privacy policy consent by user and version.

    사용자·버전별 개인정보 고지 동의 기록.
    """

    __tablename__ = "privacy_consents"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PantryItem(Base):
    """Tea/coffee pantry inventory row (S5 router consumes this table).

    차·커피 찻장 재고 행 (S5 라우터가 이 테이블을 사용한다).
    """

    __tablename__ = "pantry_items"
    __table_args__ = (
        CheckConstraint("kind IN ('tea', 'coffee', 'other')", name="ck_pantry_items_kind"),
        CheckConstraint(
            "remaining_pct IN (0, 25, 50, 75, 100)", name="ck_pantry_items_remaining_pct"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(10))
    remaining_pct: Mapped[int] = mapped_column(Integer())
    capacity_g: Mapped[int | None] = mapped_column(Integer())
    note: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserMemory(Base):
    """Current per-user memory summary.

    사용자별 현재 메모리 요약.
    """

    __tablename__ = "user_memory"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserMemoryHistory(Base):
    """One-generation history for overwritten user memory.

    덮어쓴 사용자 메모리의 1세대 이력.
    """

    __tablename__ = "user_memory_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    replaced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
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

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Free-text memo: who this code is meant for.
    # 누구에게 줄 코드인지 적는 자유 메모.
    note: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
