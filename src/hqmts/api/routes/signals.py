"""Signals API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.models.signal import SignalORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.db.repositories.signal_repo import SignalRepository

router = APIRouter(prefix="/signals", tags=["signals"])


def _signal_to_dict(s: SignalORM) -> dict:
    return {
        "signal_id": s.signal_id,
        "strategy_instance_id": s.strategy_instance_id,
        "instrument_id": s.instrument_id,
        "signal_type": s.signal_type,
        "side": s.side,
        "cycle": s.cycle,
        "decision_time": s.decision_time.isoformat() if s.decision_time else None,
        "valid_until": s.valid_until.isoformat() if s.valid_until else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/")
async def list_signals(
    strategy_instance_id: str | None = Query(None),
    instrument_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List signals with optional filtering."""
    repo = BaseRepository(SignalORM, db)
    filters: dict = {}
    if strategy_instance_id:
        filters["strategy_instance_id"] = strategy_instance_id
    if instrument_id:
        filters["instrument_id"] = instrument_id
    signals = await repo.get_many(filters=filters or None, limit=limit)
    total = await repo.count(filters=filters or None)
    return {"signals": [_signal_to_dict(s) for s in signals], "total": total}


@router.get("/{signal_id}")
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get signal details with full traceability chain."""
    repo = SignalRepository(db)
    signal = await repo.get_by_id(signal_id, id_column="signal_id")
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _signal_to_dict(signal)
