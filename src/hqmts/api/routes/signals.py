"""Signals API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.models.instrument import InstrumentORM
from hqmts.db.models.signal import SignalORM
from hqmts.db.models.strategy import StrategyInstanceORM, StrategyORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.db.repositories.signal_repo import SignalRepository

router = APIRouter(prefix="/signals", tags=["signals"])


def _signal_to_dict(s: SignalORM, *, strategy_id: str | None = None, strategy_name: str | None = None) -> dict:
    return {
        "signal_id": s.signal_id,
        "strategy_id": strategy_id or s.strategy_instance_id,
        "strategy_instance_id": s.strategy_instance_id,
        "strategy_name": strategy_name or s.strategy_instance_id,
        "instrument_id": s.instrument_id,
        "signal_type": s.signal_type,
        "side": s.target_direction,
        "direction": s.target_direction,
        "cycle": s.cycle,
        "strength": s.signal_strength,
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

    result = []
    for s in signals:
        # Enrich with strategy info
        si_stmt = select(StrategyInstanceORM).where(
            StrategyInstanceORM.strategy_instance_id == s.strategy_instance_id
        )
        si_res = await db.execute(si_stmt)
        si = si_res.scalar_one_or_none()

        strategy_id = si.strategy_id if si else None
        strategy_name = None
        if si:
            strat_stmt = select(StrategyORM).where(StrategyORM.strategy_id == si.strategy_id)
            strat_res = await db.execute(strat_stmt)
            strat = strat_res.scalar_one_or_none()
            strategy_name = strat.name if strat else None

        d = _signal_to_dict(s, strategy_id=strategy_id, strategy_name=strategy_name)

        # Enrich with instrument info
        inst_stmt = select(InstrumentORM).where(InstrumentORM.instrument_id == s.instrument_id)
        inst_res = await db.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        d["instrument_code"] = inst.symbol if inst else s.instrument_id

        d["price_target"] = None
        result.append(d)
    return {"signals": result, "total": total}


@router.get("/{signal_id}")
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get signal details with full traceability chain."""
    repo = SignalRepository(db)
    signal = await repo.get_by_id(signal_id, id_column="signal_id")
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Enrich with strategy info
    si_stmt = select(StrategyInstanceORM).where(
        StrategyInstanceORM.strategy_instance_id == signal.strategy_instance_id
    )
    si_res = await db.execute(si_stmt)
    si = si_res.scalar_one_or_none()

    strategy_id = si.strategy_id if si else None
    strategy_name = None
    if si:
        strat_stmt = select(StrategyORM).where(StrategyORM.strategy_id == si.strategy_id)
        strat_res = await db.execute(strat_stmt)
        strat = strat_res.scalar_one_or_none()
        strategy_name = strat.name if strat else None

    return _signal_to_dict(signal, strategy_id=strategy_id, strategy_name=strategy_name)
