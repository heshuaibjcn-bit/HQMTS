"""Orders API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.api.deps_auth import get_current_user
from hqmts.core.enums import OrderStatus
from hqmts.db.models.instrument import InstrumentORM
from hqmts.db.models.order import OrderORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.db.repositories.order_repo import OrderRepository

router = APIRouter(prefix="/orders", tags=["orders"])

# States from which cancellation is allowed
_CANCELLABLE_STATUSES = {
    OrderStatus.CREATED,
    OrderStatus.PENDING_SUBMIT,
    OrderStatus.SUBMITTED,
    OrderStatus.ACCEPTED,
    OrderStatus.PARTIAL_FILLED,
}


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

    result = []
    for o in orders:
        d = _order_to_dict(o)
        # Enrich with instrument info
        inst_stmt = select(InstrumentORM).where(InstrumentORM.instrument_id == o.instrument_id)
        inst_result = await db.execute(inst_stmt)
        inst = inst_result.scalar_one_or_none()
        d["instrument_code"] = inst.symbol if inst else o.instrument_id
        d["instrument_name"] = inst.name if inst else ""
        d["direction"] = o.side
        result.append(d)
    return {"orders": result, "total": total}


@router.get("/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get order details with full lifecycle traceability."""
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id, id_column="order_id")
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_dict(order)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Cancel a pending or submitted order (PRD FR-UI-003).

    Only orders in cancellable states (created, pending_submit, pending,
    submitted, accepted, partial_filled) can be cancelled.
    """
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id, id_column="order_id")
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        current_status = OrderStatus(order.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown order status: {order.status}")

    if current_status not in _CANCELLABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Order in status '{order.status}' cannot be cancelled. "
            f"Cancellable: {[s.value for s in _CANCELLABLE_STATUSES]}",
        )

    order.status = OrderStatus.CANCELED.value
    await db.commit()
    await db.refresh(order)
    return {
        **_order_to_dict(order),
        "cancelled_by": user.user_id,
    }
