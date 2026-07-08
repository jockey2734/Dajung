"""Schema sanity checks on ORM metadata — no database needed.

ORM 메타데이터 스키마 검증 — 데이터베이스 불필요.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint

import api.app.db.models  # noqa: F401 — register tables on Base.metadata
from api.app.db.base import Base


def test_tables_registered() -> None:
    assert {"users", "invitation_codes"} <= set(Base.metadata.tables)


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
    names = {c.name for c in users.constraints if isinstance(c, CheckConstraint)}
    assert {"ck_users_role", "ck_users_status"} <= names


def test_invitation_code_links_to_users() -> None:
    codes = Base.metadata.tables["invitation_codes"]
    referenced = {fk.column.table.name for fk in codes.foreign_keys}
    assert referenced == {"users"}
