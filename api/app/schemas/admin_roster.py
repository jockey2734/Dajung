"""Semester roster administration schemas.

학기별 명단 관리 스키마.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SEMESTER_PATTERN = r"^\d{4}-[12]$"


class RosterCreateRequest(BaseModel):
    semester: str = Field(pattern=SEMESTER_PATTERN)
    department: str = Field(min_length=1, max_length=30)
    member_name: str = Field(min_length=1, max_length=100)
    position: str | None = Field(default=None, max_length=30)
    user_id: uuid.UUID | None = None


class RosterUpdateRequest(BaseModel):
    semester: str | None = Field(default=None, pattern=SEMESTER_PATTERN)
    department: str | None = Field(default=None, min_length=1, max_length=30)
    member_name: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = Field(default=None, max_length=30)
    user_id: uuid.UUID | None = None


class RosterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    semester: str
    department: str
    member_name: str
    position: str | None
    user_id: uuid.UUID | None
    created_at: datetime
