"""Strategies API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.models.strategy import StrategyORM, StrategyInstanceORM
from hqmts.db.repositories.base import BaseRepository

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _strategy_to_dict(s: StrategyORM) -> dict:
    return {
        "strategy_id": s.strategy_id,
        "name": s.name,
        "version": s.version,
        "description": s.description,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _instance_to_dict(i: StrategyInstanceORM, strategy_name: str = "") -> dict:
    instruments = []
    try:
        instruments = json.loads(i.instruments_json) if i.instruments_json else []
    except (json.JSONDecodeError, TypeError):
        instruments = []
    return {
        "instance_id": i.strategy_instance_id,
        "strategy_instance_id": i.strategy_instance_id,
        "strategy_id": i.strategy_id,
        "strategy_name": strategy_name,
        "status": i.status,
        "environment": i.environment,
        "instrument_codes": instruments,
        "started_at": i.created_at.isoformat() if i.created_at else None,
        "pnl": 0,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


@router.get("/")
async def list_strategies(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List strategies."""
    repo = BaseRepository(StrategyORM, db)
    filters: dict = {}
    if status:
        filters["status"] = status
    strategies = await repo.get_many(filters=filters or None, limit=limit)
    total = await repo.count(filters=filters or None)
    return {"strategies": [_strategy_to_dict(s) for s in strategies], "total": total}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get strategy details."""
    repo = BaseRepository(StrategyORM, db)
    strategy = await repo.get_by_id(strategy_id, id_column="strategy_id")
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _strategy_to_dict(strategy)


@router.get("/{strategy_id}/instances")
async def list_strategy_instances(
    strategy_id: str,
    environment: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List running instances of a strategy."""
    repo = BaseRepository(StrategyInstanceORM, db)
    filters: dict = {"strategy_id": strategy_id}
    if environment:
        filters["environment"] = environment
    instances = await repo.get_many(filters=filters, limit=100)

    # Look up strategy name
    strat_stmt = select(StrategyORM).where(StrategyORM.strategy_id == strategy_id)
    strat_result = await db.execute(strat_stmt)
    strat = strat_result.scalar_one_or_none()
    strategy_name = strat.name if strat else strategy_id

    return {"instances": [_instance_to_dict(i, strategy_name) for i in instances]}
