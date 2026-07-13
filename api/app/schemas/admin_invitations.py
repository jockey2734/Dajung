"""Invitation administration API schemas.

통과번호 관리 API 스키마.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InvitationCreateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    days: int = 7


class InvitationOut(BaseModel):
    id: uuid.UUID
    note: str | None
    expires_at: datetime
    status: Literal["활성", "만료", "사용됨"]
    used_at: datetime | None


class InvitationCreatedOut(BaseModel):
    id: uuid.UUID
    code: str
    note: str | None
    expires_at: datetime
