"""Pantry CRUD routes — S5 feature.

찻장 항목 관리 라우터.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, cast

from fastapi import APIRouter
from sqlalchemy import select

from api.app.core.deps import CurrentUser, SessionDep
from api.app.core.errors import ApiError
from api.app.db.models import PantryItem, User
from api.app.schemas.pantry import (
    CoffeeAlertOut,
    PantryItemCreate,
    PantryItemOut,
    PantryItemResponse,
    PantryItemUpdate,
    PantryListResponse,
    PantryUserOut,
)

router = APIRouter(prefix="/pantry", tags=["pantry"])

COFFEE_ALERT_THRESHOLD_G = 500


def _build_item_out(item: PantryItem, user: User) -> PantryItemOut:
    estimated_g = None
    if item.kind == "coffee" and item.capacity_g is not None:
        estimated_g = item.capacity_g * item.remaining_pct // 100

    return PantryItemOut(
        id=item.id,
        name=item.name,
        kind=cast(Literal["tea", "coffee", "other"], item.kind),
        remaining_pct=cast(Literal[0, 25, 50, 75, 100], item.remaining_pct),
        capacity_g=item.capacity_g,
        estimated_g=estimated_g,
        note=item.note,
        updated_by=PantryUserOut(id=user.id, name=user.name),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _calculate_coffee_alert(items: list[PantryItem]) -> CoffeeAlertOut:
    total = 0
    for item in items:
        if item.kind == "coffee" and item.capacity_g is not None:
            total += item.capacity_g * item.remaining_pct // 100
    return CoffeeAlertOut(
        alert=total < COFFEE_ALERT_THRESHOLD_G,
        total_estimated_g=total,
        threshold_g=COFFEE_ALERT_THRESHOLD_G,
    )


@router.get("")
async def get_pantry_items(
    current_user: CurrentUser,
    session: SessionDep,
    sort: Literal["updated_at", "name", "remaining_pct"] = "updated_at",
    order: Literal["asc", "desc"] = "desc",
) -> PantryListResponse:
    # We join with User to get updated_by details.
    stmt = select(PantryItem, User).join(User, PantryItem.updated_by == User.id)

    col: Any = PantryItem.updated_at
    if sort == "name":
        col = PantryItem.name
    elif sort == "remaining_pct":
        col = PantryItem.remaining_pct

    stmt = stmt.order_by(col.asc()) if order == "asc" else stmt.order_by(col.desc())

    result = await session.execute(stmt)
    rows = result.all()

    pantry_items = [row[0] for row in rows]

    out_items = [_build_item_out(row[0], row[1]) for row in rows]
    coffee_alert = _calculate_coffee_alert(pantry_items)

    return PantryListResponse(items=out_items, coffee_alert=coffee_alert)


@router.post("", status_code=201)
async def create_pantry_item(
    req: PantryItemCreate, current_user: CurrentUser, session: SessionDep
) -> PantryItemResponse:
    new_item = PantryItem(
        name=req.name,
        kind=req.kind,
        remaining_pct=req.remaining_pct,
        capacity_g=req.capacity_g,
        note=req.note,
        updated_by=current_user.id,
    )
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)

    # Recalculate coffee alert for the response
    all_items_stmt = select(PantryItem)
    all_items_res = await session.execute(all_items_stmt)
    all_items = [row[0] for row in all_items_res.all()]
    coffee_alert = _calculate_coffee_alert(all_items)

    return PantryItemResponse(
        item=_build_item_out(new_item, current_user), coffee_alert=coffee_alert
    )


@router.patch("/{item_id}")
async def update_pantry_item(
    item_id: uuid.UUID,
    req: PantryItemUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> PantryItemResponse:
    stmt = select(PantryItem).where(PantryItem.id == item_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise ApiError(404, "item_not_found", "항목을 찾을 수 없습니다.")

    if req.name is not None:
        item.name = req.name
    if req.kind is not None:
        item.kind = req.kind
    if req.remaining_pct is not None:
        item.remaining_pct = req.remaining_pct
    if req.capacity_g is not None:
        item.capacity_g = req.capacity_g
    if req.note is not None:
        item.note = req.note

    item.updated_by = current_user.id
    await session.commit()
    await session.refresh(item)

    all_items_stmt = select(PantryItem)
    all_items_res = await session.execute(all_items_stmt)
    all_items = [row[0] for row in all_items_res.all()]
    coffee_alert = _calculate_coffee_alert(all_items)

    return PantryItemResponse(item=_build_item_out(item, current_user), coffee_alert=coffee_alert)


@router.delete("/{item_id}", status_code=204)
async def delete_pantry_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> None:
    stmt = select(PantryItem).where(PantryItem.id == item_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise ApiError(404, "item_not_found", "항목을 찾을 수 없습니다.")

    await session.delete(item)
    await session.commit()
