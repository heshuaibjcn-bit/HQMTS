"""Instruments API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.models.instrument import InstrumentORM
from hqmts.db.repositories.base import BaseRepository

router = APIRouter(prefix="/instruments", tags=["instruments"])


def _instrument_to_dict(inst: InstrumentORM) -> dict:
    return {
        "instrument_id": inst.instrument_id,
        "ts_code": inst.ts_code,
        "exchange": inst.exchange,
        "symbol": inst.symbol,
        "name": inst.name,
        "board_type": inst.board_type,
        "lot_size": inst.lot_size,
    }


@router.get("/")
async def list_instruments(
    exchange: str | None = Query(None, description="Filter by exchange"),
    board_type: str | None = Query(None, description="Filter by board type"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List instruments with optional filtering."""
    repo = BaseRepository(InstrumentORM, db)
    filters: dict = {}
    if exchange:
        filters["exchange"] = exchange
    if board_type:
        filters["board_type"] = board_type
    instruments = await repo.get_many(filters=filters or None, limit=limit)
    total = await repo.count(filters=filters or None)
    return {"instruments": [_instrument_to_dict(i) for i in instruments], "total": total}


@router.get("/{instrument_id}")
async def get_instrument(
    instrument_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get instrument details."""
    repo = BaseRepository(InstrumentORM, db)
    inst = await repo.get_by_id(instrument_id, id_column="instrument_id")
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return _instrument_to_dict(inst)
