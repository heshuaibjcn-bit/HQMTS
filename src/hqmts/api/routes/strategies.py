"""Strategies API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/")
async def list_strategies(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List strategies."""
    return {"strategies": [], "total": 0}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get strategy details."""
    return {"strategy_id": strategy_id}


@router.get("/{strategy_id}/instances")
async def list_strategy_instances(
    strategy_id: str,
    environment: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List running instances of a strategy."""
    return {"instances": []}
