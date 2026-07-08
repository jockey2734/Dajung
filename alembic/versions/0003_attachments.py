"""create attachments table

대화 첨부 테이블 생성 (webapp-spec S2).

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        # Nullable until POST /chat/stream sends the attachment in a turn.
        # POST /chat/stream에서 첨부를 전송하기 전까지는 NULL 허용.
        sa.Column(
            "session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=True
        ),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("parsed_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("parsed_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parse_status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("promoted_doc_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "parse_status IN ('pending', 'parsed', 'failed')",
            name="ck_attachments_parse_status",
        ),
    )
    op.create_index("ix_attachments_user_id", "attachments", ["user_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_user_id", table_name="attachments")
    op.drop_table("attachments")
