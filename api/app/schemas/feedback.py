"""Request and response schemas for message feedback.

메시지 피드백 요청·응답 스키마.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = None


class FeedbackResponse(BaseModel):
    message_id: uuid.UUID
    rating: Literal[-1, 1]
    comment: str | None
