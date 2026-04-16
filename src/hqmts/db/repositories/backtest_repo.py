"""Backtest result repository."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.backtest.result import BacktestResult
from hqmts.db.models.backtest import BacktestResultORM
from hqmts.db.repositories.base import BaseRepository


class BacktestResultRepository(BaseRepository[BacktestResultORM]):
    """Repository for backtest result persistence."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(BacktestResultORM, session)

    async def get_by_backtest_id(self, backtest_id: str) -> BacktestResult | None:
        """Get a backtest result by its backtest_id."""
        stmt = select(BacktestResultORM).where(BacktestResultORM.backtest_id == backtest_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _orm_to_result(orm) if orm else None

    async def get_by_strategy(
        self,
        strategy_name: str,
        limit: int = 20,
    ) -> list[BacktestResult]:
        """Get backtest results by strategy name."""
        stmt = (
            select(BacktestResultORM)
            .where(BacktestResultORM.strategy_name == strategy_name)
            .order_by(BacktestResultORM.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_orm_to_result(orm) for orm in result.scalars().all()]

    async def get_by_date_range(
        self,
        start: str,
        end: str,
        limit: int = 20,
    ) -> list[BacktestResult]:
        """Get backtest results within a date range."""
        stmt = (
            select(BacktestResultORM)
            .where(
                BacktestResultORM.start_date >= start,
                BacktestResultORM.end_date <= end,
            )
            .order_by(BacktestResultORM.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_orm_to_result(orm) for orm in result.scalars().all()]

    async def save(self, bt_result: BacktestResult) -> BacktestResultORM:
        """Save a backtest result."""
        orm = _result_to_orm(bt_result)
        self._session.add(orm)
        await self._session.flush()
        return orm


def _result_to_orm(r: BacktestResult) -> BacktestResultORM:
    """Convert BacktestResult domain object to ORM."""
    return BacktestResultORM(
        backtest_id=r.backtest_id,
        strategy_name=r.strategy_name,
        strategy_version=r.strategy_version,
        strategy_params=json.dumps(r.strategy_params),
        instruments=json.dumps(r.instruments),
        cycle=r.cycle,
        start_date=r.start_date,
        end_date=r.end_date,
        initial_cash=r.initial_cash,
        final_total_asset=r.final_total_asset,
        total_return=r.total_return,
        annualized_return=r.annualized_return,
        max_drawdown=r.max_drawdown,
        sharpe_ratio=r.sharpe_ratio,
        total_trades=r.total_trades,
        win_rate=r.win_rate,
        profit_factor=r.profit_factor,
        trades=json.dumps(r.trades),
        daily_values=json.dumps(r.daily_values),
        cost_summary=json.dumps(r.cost_summary),
        data_version=r.data_version,
        created_at=r.created_at,
    )


def _orm_to_result(orm: BacktestResultORM) -> BacktestResult:
    """Convert ORM to BacktestResult domain object."""
    return BacktestResult(
        backtest_id=orm.backtest_id,
        strategy_name=orm.strategy_name,
        strategy_version=orm.strategy_version,
        strategy_params=json.loads(orm.strategy_params),
        instruments=json.loads(orm.instruments),
        cycle=orm.cycle,
        start_date=orm.start_date,
        end_date=orm.end_date,
        initial_cash=orm.initial_cash,
        final_total_asset=orm.final_total_asset,
        total_return=orm.total_return,
        annualized_return=orm.annualized_return,
        max_drawdown=orm.max_drawdown,
        sharpe_ratio=orm.sharpe_ratio,
        total_trades=orm.total_trades,
        win_rate=orm.win_rate,
        profit_factor=orm.profit_factor,
        trades=json.loads(orm.trades),
        daily_values=json.loads(orm.daily_values),
        cost_summary=json.loads(orm.cost_summary),
        data_version=orm.data_version,
        created_at=orm.created_at,
    )
