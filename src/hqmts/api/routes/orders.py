"""Orders API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.models.order import OrderORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.db.repositories.order_repo import OrderRepository

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_dict(o: OrderORM) -> dict:
    return {
        "order_id": o.order_id,
        "account_id": o.account_id,
        "instrument_id": o.instrument_id,
        "side": o.side,
        "price": str(o.price),
        "quantity": o.quantity,
        "filled_quantity": o.filled_quantity,
        "status": o.status,
        "order_type": o.order_type,
        "broker_order_id": o.broker_order_id,
        "reject_reason": o.reject_reason,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


@router.get("/")
async def list_orders(
    account_id: str | None = Query(None),
    instrument_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List orders with optional filtering."""
    repo = BaseRepository(OrderORM, db)
    filters: dict = {}
    if account_id:
        filters["account_id"] = account_id
    if instrument_id:
        filters["instrument_id"] = instrument_id
    if status:
        filters["status"] = status
    orders = await repo.get_many(filters=filters or None, limit=limit)
    total = await repo.count(filters=filters or None)
    return {"orders": [_order_to_dict(o) for o in orders], "total": total}


@router.get("/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get order details with full lifecycle traceability."""
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id, id_column="order_id")
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_dict(order)
