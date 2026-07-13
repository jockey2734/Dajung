"""add admin role, account terms, and president audit tables

관리자 역할·계정 임기·회장 이양 감사 테이블 추가.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _seven_months_from_now() -> datetime:
    now = datetime.now(UTC)
    month_index = now.year * 12 + (now.month - 1) + 7
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    return now.replace(
        year=year,
        month=month,
        day=min(now.day, monthrange(year, month)[1]),
    )


def upgrade() -> None:
    op.add_column("users", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    users = sa.table(
        "users",
        sa.column("role", sa.String()),
        sa.column("expires_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        users.update().where(users.c.role != "owner").values(expires_at=_seven_months_from_now())
    )

    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('owner', 'president', 'staff')")
    op.create_index(
        "uq_users_single_president",
        "users",
        ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'president'"),
        sqlite_where=sa.text("role = 'president'"),
    )

    op.create_table(
        "president_transfers",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("from_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("to_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "staff_semesters",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("semester", sa.String(7), nullable=False),
        sa.Column("department", sa.String(30), nullable=False),
        sa.Column("member_name", sa.String(100), nullable=False),
        sa.Column("position", sa.String(30)),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("semester ~ '^[0-9]{4}-[12]$'", name="ck_staff_semesters_semester"),
        sa.UniqueConstraint("semester", "member_name", name="uq_staff_semesters_semester_member"),
    )


def downgrade() -> None:
    op.drop_table("staff_semesters")
    op.drop_table("president_transfers")
    op.drop_index("uq_users_single_president", table_name="users")
    users = sa.table("users", sa.column("role", sa.String()))
    op.execute(users.update().where(users.c.role == "president").values(role="staff"))
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('owner', 'staff')")
    op.drop_column("users", "expires_at")
