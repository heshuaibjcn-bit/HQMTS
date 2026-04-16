"""Orders API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/")
async def list_orders(
    account_id: str | None = Query(None),
    instrument_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List orders with optional filtering."""
    return {"orders": [], "total": 0}


@router.get("/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get order details with full lifecycle traceability."""
    return {"order_id": order_id}
