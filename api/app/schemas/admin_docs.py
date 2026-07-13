"""Knowledge-document administration schemas.

지식 문서 관리 스키마.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DocumentUploadOut(BaseModel):
    folder: str
    filename: str
    status: Literal["processing"] = "processing"
