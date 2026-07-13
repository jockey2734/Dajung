"""President administration API schemas.

회장 권한 관리 API 스키마.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PresidentTransferRequest(BaseModel):
    to_user_id: uuid.UUID
    note: str | None = Field(default=None, max_length=1000)


class PresidentUserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    role: str
    title: str | None
    expires_at: datetime | None


class PresidentTransferOut(BaseModel):
    id: uuid.UUID
    from_user: PresidentUserOut | None
    to_user: PresidentUserOut
    actor: PresidentUserOut
    note: str | None
    created_at: datetime
