"""Tests for backtest result repository and API routes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from hqmts.backtest.result import BacktestResult
from hqmts.db.repositories.backtest_repo import (
    BacktestResultRepository,
    _orm_to_result,
    _result_to_orm,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _sample_result(**overrides) -> BacktestResult:
    defaults = {
        "backtest_id": "bt-001",
        "strategy_name": "dual_ma",
        "strategy_version": "v1",
        "strategy_params": {"fast_period": 3, "slow_period": 5},
        "instruments": ["000001.SZ"],
        "cycle": "5m",
        "start_date": "20240102",
        "end_date": "20240103",
        "initial_cash": Decimal("1000000"),
        "final_total_asset": Decimal("1050000"),
        "total_return": Decimal("5"),
        "annualized_return": Decimal("1825"),
        "max_drawdown": Decimal("2"),
        "sharpe_ratio": Decimal("1.5"),
        "total_trades": 10,
        "win_rate": Decimal("60"),
        "profit_factor": Decimal("1.8"),
        "trades": [],
        "daily_values": [],
        "cost_summary": {"total_commission": "50", "total_stamp_tax": "10"},
        "data_version": "v1",
        "created_at": datetime(2024, 1, 4, 12, 0),
    }
    defaults.update(overrides)
    return BacktestResult(**defaults)


# ── BacktestResultRepository Tests ───────────────────────────────────────────


class TestBacktestResultRepository:
    def _make_repo(self) -> tuple[BacktestResultRepository, AsyncMock]:
        session = AsyncMock()
        repo = BacktestResultRepository(session)
        return repo, session

    @pytest.mark.asyncio
    async def test_get_by_backtest_id(self):
        repo, session = self._make_repo()

        orm = _result_to_orm(_sample_result())
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = orm
        session.execute = AsyncMock(return_value=exec_result)

        result = await repo.get_by_backtest_id("bt-001")
        assert result is not None
        assert result.backtest_id == "bt-001"
        assert result.strategy_name == "dual_ma"

    @pytest.mark.asyncio
    async def test_get_by_backtest_id_not_found(self):
        repo, session = self._make_repo()

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)

        result = await repo.get_by_backtest_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save(self):
        repo, session = self._make_repo()

        bt = _sample_result()
        orm = await repo.save(bt)
        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert orm.backtest_id == "bt-001"

    @pytest.mark.asyncio
    async def test_get_by_strategy(self):
        repo, session = self._make_repo()

        orm = _result_to_orm(_sample_result())
        scalar_result = MagicMock()
        scalar_result.all.return_value = [orm]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalar_result
        session.execute = AsyncMock(return_value=exec_result)

        results = await repo.get_by_strategy("dual_ma")
        assert len(results) == 1
        assert results[0].strategy_name == "dual_ma"


# ── ORM Mapping Tests ────────────────────────────────────────────────────────


class TestBacktestResultMapping:
    def test_round_trip(self):
        bt = _sample_result()
        orm = _result_to_orm(bt)
        assert orm.backtest_id == "bt-001"
        assert orm.strategy_name == "dual_ma"
        assert orm.total_trades == 10

        bt2 = _orm_to_result(orm)
        assert bt2.backtest_id == bt.backtest_id
        assert bt2.strategy_name == bt.strategy_name
        assert bt2.total_trades == bt.total_trades
        assert bt2.initial_cash == bt.initial_cash
        assert bt2.instruments == bt.instruments

    def test_json_fields_round_trip(self):
        bt = _sample_result(
            strategy_params={"fast_period": 5, "slow_period": 20},
            trades=[{"trade_id": "T-001", "side": "buy", "price": "10.00"}],
            daily_values=[{"trade_date": "2024-01-02", "total_asset": "1000000"}],
        )
        orm = _result_to_orm(bt)
        bt2 = _orm_to_result(orm)
        assert bt2.strategy_params == bt.strategy_params
        assert bt2.trades == bt.trades
        assert bt2.daily_values == bt.daily_values
