"""create chat serving tables

채팅 서빙 테이블 생성 (webapp-spec S1).

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'deleted')", name="ck_chat_sessions_status"
        ),
    )
    # Sidebar query: my sessions, most recent first (webapp-plan §5).
    # 사이드바 쿼리: 내 세션 최신순 (webapp-plan §5).
    op.create_index("ix_chat_sessions_user_recent", "chat_sessions", ["user_id", "last_message_at"])

    op.create_table(
        "messages",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False, server_default="markdown"),
        sa.Column(
            "parent_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True
        ),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="completed"),
        sa.Column("error_code", sa.String(30), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        sa.CheckConstraint(
            "status IN ('completed', 'streaming', 'failed', 'deleted')", name="ck_messages_status"
        ),
        sa.UniqueConstraint("session_id", "sequence_no", name="uq_messages_session_seq"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "model_runs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column(
            "session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False
        ),
        sa.Column("model_provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("finish_reason", sa.String(50), nullable=True),
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "retrieval_events",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column(
            "model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id"), nullable=True
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("chunks", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "feedbacks",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("rating IN (-1, 1)", name="ck_feedbacks_rating"),
        sa.UniqueConstraint("message_id", "user_id", name="uq_feedbacks_message_user"),
    )

    op.create_table(
        "privacy_consents",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("version", sa.String(50), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "pantry_items",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("remaining_pct", sa.Integer(), nullable=False),
        sa.Column("capacity_g", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("kind IN ('tea', 'coffee', 'other')", name="ck_pantry_items_kind"),
        sa.CheckConstraint(
            "remaining_pct IN (0, 25, 50, 75, 100)", name="ck_pantry_items_remaining_pct"
        ),
    )

    op.create_table(
        "user_memory",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "user_memory_history",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "replaced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_memory_history")
    op.drop_table("user_memory")
    op.drop_table("pantry_items")
    op.drop_table("privacy_consents")
    op.drop_table("feedbacks")
    op.drop_table("retrieval_events")
    op.drop_table("model_runs")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chat_sessions_user_recent", table_name="chat_sessions")
    op.drop_table("chat_sessions")
