"""Tests for BacktestRunner and parameter sweep."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.backtest.runner import BacktestRunner
from hqmts.backtest.registry import register_strategy
from hqmts.backtest.strategy import DualMACrossoverStrategy
from hqmts.core.enums import Cycle
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.domain.bar import Bar


# ── Helpers ──────────────────────────────────────────────────────────────────


def _bar(start: datetime, close: str = "10.00", volume: int = 100000) -> Bar:
    return Bar(
        instrument_id=InstrumentId("000001.SZ"),
        cycle=Cycle.M5,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes=5),
        open=Decimal(close),
        high=Decimal(close) + Decimal("0.50"),
        low=Decimal(close) - Decimal("0.50"),
        close=Decimal(close),
        volume=volume,
        amount=Decimal("1000000"),
        is_completed=True,
        source="test",
        data_version=VersionStr("v1"),
    )


def _golden_cross_bars() -> list[Bar]:
    """Bars that produce a golden cross: declining then rising."""
    closes = (
        ["10.00", "9.80", "9.60", "9.50", "9.40", "9.30", "9.40", "9.50", "9.60", "9.70"]
        + ["9.80", "10.00", "10.20", "10.30", "10.40", "10.50", "10.60", "10.70", "10.80", "10.90"]
        + ["11.00", "11.10", "11.20", "11.30", "11.40", "11.50", "11.60", "11.70", "11.80", "11.90"]
    )
    return [_bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c) for i, c in enumerate(closes)]


# ── BacktestRunner Tests ─────────────────────────────────────────────────────


class TestBacktestRunner:
    @pytest.fixture(autouse=True)
    def setup_registry(self):
        """Ensure dual_ma is registered."""
        register_strategy("dual_ma", DualMACrossoverStrategy, {"fast_period": 5, "slow_period": 20})

    @pytest.mark.asyncio
    async def test_run_backtest_with_bars(self):
        runner = BacktestRunner(db_session=None)
        bars = _golden_cross_bars()
        result = await runner.run_backtest(
            strategy_name="dual_ma",
            strategy_params={"fast_period": 3, "slow_period": 5},
            instruments=["000001.SZ"],
            cycle="5m",
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
            bars_by_instrument={"000001.SZ": bars},
        )
        assert result.strategy_name == "dual_ma"
        assert result.total_trades >= 1

    @pytest.mark.asyncio
    async def test_run_backtest_unknown_strategy(self):
        runner = BacktestRunner(db_session=None)
        with pytest.raises(ValueError, match="Unknown strategy"):
            await runner.run_backtest(
                strategy_name="nonexistent",
                strategy_params={},
                instruments=["000001.SZ"],
                cycle="5m",
                start_date="20240102",
                end_date="20240103",
            )

    @pytest.mark.asyncio
    async def test_run_backtest_no_bars(self):
        runner = BacktestRunner(db_session=None)
        with pytest.raises(ValueError, match="No bar data"):
            await runner.run_backtest(
                strategy_name="dual_ma",
                strategy_params={"fast_period": 3, "slow_period": 5},
                instruments=["000001.SZ"],
                cycle="5m",
                start_date="20240102",
                end_date="20240103",
            )

    @pytest.mark.asyncio
    async def test_parameter_sweep(self):
        runner = BacktestRunner(db_session=None)
        bars = _golden_cross_bars()
        sweep = await runner.run_parameter_sweep(
            strategy_name="dual_ma",
            param_grid={"fast_period": [3, 5], "slow_period": [10, 15]},
            instruments=["000001.SZ"],
            cycle="5m",
            start_date="20240102",
            end_date="20240103",
            bars_by_instrument={"000001.SZ": bars},
        )
        assert len(sweep.results) == 4  # 2 x 2 combinations
        # Results sorted by total_return descending
        for i in range(len(sweep.results) - 1):
            assert sweep.results[i].total_return >= sweep.results[i + 1].total_return
        assert sweep.failed_runs == 0

    @pytest.mark.asyncio
    async def test_parameter_sweep_single_param(self):
        runner = BacktestRunner(db_session=None)
        bars = _golden_cross_bars()
        sweep = await runner.run_parameter_sweep(
            strategy_name="dual_ma",
            param_grid={"fast_period": [3, 5, 7]},
            instruments=["000001.SZ"],
            cycle="5m",
            start_date="20240102",
            end_date="20240103",
            bars_by_instrument={"000001.SZ": bars},
        )
        assert len(sweep.results) == 3

    @pytest.mark.asyncio
    async def test_parameter_sweep_unknown_strategy(self):
        runner = BacktestRunner(db_session=None)
        with pytest.raises(ValueError, match="Unknown strategy"):
            await runner.run_parameter_sweep(
                strategy_name="nonexistent",
                param_grid={"fast_period": [3]},
                instruments=["000001.SZ"],
                cycle="5m",
                start_date="20240102",
                end_date="20240103",
            )

    @pytest.mark.asyncio
    async def test_run_backtest_uses_default_params(self):
        """Merged params should include defaults from registry."""
        runner = BacktestRunner(db_session=None)
        bars = _golden_cross_bars()
        result = await runner.run_backtest(
            strategy_name="dual_ma",
            strategy_params={},  # No overrides, use defaults
            instruments=["000001.SZ"],
            cycle="5m",
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
            bars_by_instrument={"000001.SZ": bars},
        )
        assert result.strategy_params["fast_period"] == 5
        assert result.strategy_params["slow_period"] == 20
