"""Instruments API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("/")
async def list_instruments(
    exchange: str | None = Query(None, description="Filter by exchange"),
    board_type: str | None = Query(None, description="Filter by board type"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List instruments with optional filtering."""
    # Placeholder — in production, use InstrumentRepository
    return {"instruments": [], "total": 0}


@router.get("/{instrument_id}")
async def get_instrument(
    instrument_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get instrument details."""
    return {"instrument_id": instrument_id}
