"""Upload response schemas — S2 conversation attachments.

업로드 응답 스키마 — S2 대화 첨부.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class AttachmentUploadOut(BaseModel):
    id: uuid.UUID
    name: str
    chars: int
    parse_status: Literal["parsed", "failed"]


class UploadResponse(BaseModel):
    attachments: list[AttachmentUploadOut]
