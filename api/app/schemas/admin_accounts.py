"""Account administration API schemas.

계정 관리 API 스키마.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    title: str | None
    role: str
    status: str
    expires_at: datetime | None
    last_seen_at: datetime | None
    must_change_password: bool


class AdminUserUpdate(BaseModel):
    expires_at: datetime | None = None
    status: Literal["active", "suspended"] | None = None
    title: str | None = Field(default=None, max_length=50)


class TemporaryPasswordOut(BaseModel):
    user_id: uuid.UUID
    temporary_password: str
