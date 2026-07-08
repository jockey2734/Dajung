"""Chat stream, session history, and file-list schemas.

채팅 스트림·세션 이력·파일 목록 스키마.
Contract: serving-plan §1·§4 + webapp-plan §5·§7.
계약: serving-plan §1·§4 + webapp-plan §5·§7.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    route: Literal["auto", "knowledge", "handover"] = "auto"
    # Continue an existing session; omit to start a new one (webapp-plan §7).
    # 기존 세션 이어가기. 생략하면 신규 생성 (webapp-plan §7).
    session_id: uuid.UUID | None = None
    # Accepted in S1, activated in S2.
    # S1에서 필드만 수용하고, S2에서 실제로 사용한다.
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)


class SessionSummary(BaseModel):
    id: uuid.UUID
    title: str
    last_message_at: datetime | None
    message_count: int


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime


class SessionDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    messages: list[MessageOut]


class FileEntry(BaseModel):
    doc_id: str
    source_file: str
    doc_type: str
    semester: str | None
    restricted: bool
    chunk_count: int


class FileListResponse(BaseModel):
    files: list[FileEntry]


class PrivacyConsentRequest(BaseModel):
    version: str = Field(min_length=1, max_length=50)


class PrivacyConsentResponse(BaseModel):
    consented: bool
    version: str | None
