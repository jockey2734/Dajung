"""Schema sanity checks on ORM metadata — no database needed.

ORM 메타데이터 스키마 검증 — 데이터베이스 불필요.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

import api.app.db.models  # noqa: F401 — register tables on Base.metadata
from api.app.db.base import Base


def test_tables_registered() -> None:
    assert {
        "users",
        "invitation_codes",
        "president_transfers",
        "staff_semesters",
    } <= set(Base.metadata.tables)


def test_users_columns_match_webapp_plan() -> None:
    users = Base.metadata.tables["users"]
    expected = {
        "id",
        "email",
        "password_hash",
        "name",
        "role",
        "title",
        "status",
        "profile",
        "expires_at",
        "must_change_password",
        "last_seen_at",
        "created_at",
        "updated_at",
    }
    assert set(users.columns.keys()) == expected


def test_users_email_unique() -> None:
    users = Base.metadata.tables["users"]
    assert any(index.unique for index in users.indexes if "email" in index.columns)


def test_users_check_constraints() -> None:
    users = Base.metadata.tables["users"]
    checks = [c for c in users.constraints if isinstance(c, CheckConstraint)]
    names = {c.name for c in checks}
    assert {"ck_users_role", "ck_users_status"} <= names
    role_check = next(c for c in checks if c.name == "ck_users_role")
    assert "president" in str(role_check.sqltext)


def test_users_have_single_president_partial_index() -> None:
    users = Base.metadata.tables["users"]
    index = next(
        index
        for index in users.indexes
        if isinstance(index, Index) and index.name == "uq_users_single_president"
    )
    assert index.unique is True
    assert index.dialect_options["postgresql"]["where"] is not None
    assert index.dialect_options["sqlite"]["where"] is not None


def test_invitation_code_links_to_users() -> None:
    codes = Base.metadata.tables["invitation_codes"]
    referenced = {fk.column.table.name for fk in codes.foreign_keys}
    assert referenced == {"users"}


def test_admin_core_tables_link_to_users() -> None:
    transfers = Base.metadata.tables["president_transfers"]
    semesters = Base.metadata.tables["staff_semesters"]
    assert {fk.column.table.name for fk in transfers.foreign_keys} == {"users"}
    assert {fk.column.table.name for fk in semesters.foreign_keys} == {"users"}
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_staff_semesters_semester_member"
        for constraint in semesters.constraints
    )
