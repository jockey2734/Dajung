"""Pantry schemas — S5 feature.

찻장 요청/응답 스키마.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PantryUserOut(BaseModel):
    id: uuid.UUID
    name: str


class PantryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["tea", "coffee", "other"]
    remaining_pct: Literal[0, 25, 50, 75, 100]
    capacity_g: int | None = None
    note: str | None = None


class PantryItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    kind: Literal["tea", "coffee", "other"] | None = None
    remaining_pct: Literal[0, 25, 50, 75, 100] | None = None
    capacity_g: int | None = None
    note: str | None = None


class PantryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: Literal["tea", "coffee", "other"]
    remaining_pct: Literal[0, 25, 50, 75, 100]
    capacity_g: int | None
    estimated_g: int | None
    note: str | None
    updated_by: PantryUserOut
    created_at: datetime
    updated_at: datetime


class CoffeeAlertOut(BaseModel):
    alert: bool
    total_estimated_g: int
    threshold_g: int


class PantryListResponse(BaseModel):
    items: list[PantryItemOut]
    coffee_alert: CoffeeAlertOut
