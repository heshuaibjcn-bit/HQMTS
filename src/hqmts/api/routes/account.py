"""Account summary API route."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.api.deps_auth import get_current_user
from hqmts.db.models.account import AccountORM
from hqmts.db.models.position import PositionORM
from hqmts.db.models.strategy import StrategyInstanceORM

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/summary")
async def get_account_summary(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Get aggregated account summary (FR-API-002)."""
    # Get account data (single account for now)
    stmt = select(AccountORM).limit(1)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account is None:
        return {
            "account_id": None,
            "total_asset": 0,
            "available_cash": 0,
            "frozen_cash": 0,
            "market_value": 0,
            "pnl_intraday": 0,
            "drawdown_intraday": 0,
            "positions_count": 0,
            "active_strategies": 0,
            "risk_status": "normal",
        }

    # Count positions
    pos_count_stmt = select(func.count()).select_from(PositionORM)
    pos_result = await db.execute(pos_count_stmt)
    positions_count = pos_result.scalar_one()

    # Count active strategies
    strat_count_stmt = (
        select(func.count())
        .select_from(StrategyInstanceORM)
        .where(StrategyInstanceORM.status.in_(["paper_running", "live_running"]))
    )
    strat_result = await db.execute(strat_count_stmt)
    active_strategies = strat_result.scalar_one()

    return {
        "account_id": account.account_id,
        "total_asset": float(account.total_asset),
        "available_cash": float(account.available_cash),
        "frozen_cash": float(account.frozen_cash),
        "market_value": float(account.market_value),
        "pnl_intraday": float(account.pnl_intraday),
        "drawdown_intraday": float(account.drawdown_intraday),
        "positions_count": positions_count,
        "active_strategies": active_strategies,
        "risk_status": account.risk_status,
    }
