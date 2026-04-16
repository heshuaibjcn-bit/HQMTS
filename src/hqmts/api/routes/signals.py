"""Signals API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/")
async def list_signals(
    strategy_instance_id: str | None = Query(None),
    instrument_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List signals with optional filtering."""
    return {"signals": [], "total": 0}


@router.get("/{signal_id}")
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get signal details with full traceability chain."""
    return {"signal_id": signal_id}
