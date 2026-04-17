"""Tests for Round 3 in-blast-radius fixes."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.backtest.engine import BacktestConfig, BacktestEngine
from hqmts.backtest.registry import (
    CYCLE_MAP,
    CYCLE_MINUTES_MAP,
    VALID_CYCLE_STRINGS,
)
from hqmts.backtest.strategy import DualMACrossoverStrategy
from hqmts.core.enums import Cycle, Side
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument


def _instrument(iid: str = "000001.SZ") -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(iid),
        ts_code=iid,
        exchange="SZSE",
        symbol=iid.split(".")[0],
        name="TestStock",
    )


def _bar(
    start: datetime,
    instrument_id: str = "000001.SZ",
    close: str = "10.00",
) -> Bar:
    return Bar(
        instrument_id=InstrumentId(instrument_id),
        cycle=Cycle.M5,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes=5),
        open=Decimal(close),
        high=Decimal(close) + Decimal("0.50"),
        low=Decimal(close) - Decimal("0.50"),
        close=Decimal(close),
        volume=100000,
        amount=Decimal("1000000"),
        is_completed=True,
        source="test",
        data_version=VersionStr("v1"),
    )


# ── _has_run double-invocation guard ──────────────────────────────────────────


class TestDoubleInvocationGuard:
    def test_second_run_raises_runtime_error(self):
        """BacktestEngine.run() must raise RuntimeError on second call."""
        config = BacktestConfig(
            strategy=DualMACrossoverStrategy(),
            strategy_name="dual_ma",
            strategy_version="v1",
            strategy_params={"fast_period": 3, "slow_period": 5},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
        )
        engine = BacktestEngine(config)
        bars = [_bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i)) for i in range(5)]
        engine.run({"000001.SZ": bars})

        with pytest.raises(RuntimeError, match="already been called"):
            engine.run({"000001.SZ": bars})


# ── Cycle validation (Pydantic model_validator) ───────────────────────────────


class TestCycleValidation:
    def test_invalid_cycle_raises_value_error(self):
        """BacktestRunRequest rejects invalid cycle values."""
        from pydantic import ValidationError
        from hqmts.api.routes.backtest import BacktestRunRequest

        with pytest.raises(ValidationError, match="Invalid cycle"):
            BacktestRunRequest(
                strategy_name="dual_ma",
                strategy_params={},
                instruments=["000001.SZ"],
                cycle="2m",  # Invalid
                start_date="20240102",
                end_date="20240103",
            )

    def test_valid_cycle_accepted(self):
        """BacktestRunRequest accepts all valid cycle values."""
        from hqmts.api.routes.backtest import BacktestRunRequest

        for cycle in VALID_CYCLE_STRINGS:
            req = BacktestRunRequest(
                strategy_name="dual_ma",
                strategy_params={},
                instruments=["000001.SZ"],
                cycle=cycle,
                start_date="20240102",
                end_date="20240103",
            )
            assert req.cycle == cycle

    def test_date_order_validation(self):
        """BacktestRunRequest rejects start_date >= end_date."""
        from pydantic import ValidationError
        from hqmts.api.routes.backtest import BacktestRunRequest

        with pytest.raises(ValidationError, match="must be before"):
            BacktestRunRequest(
                strategy_name="dual_ma",
                strategy_params={},
                instruments=["000001.SZ"],
                start_date="20240103",
                end_date="20240102",  # Inverted
            )

    def test_same_date_rejected(self):
        """BacktestRunRequest rejects start_date == end_date."""
        from pydantic import ValidationError
        from hqmts.api.routes.backtest import BacktestRunRequest

        with pytest.raises(ValidationError, match="must be before"):
            BacktestRunRequest(
                strategy_name="dual_ma",
                strategy_params={},
                instruments=["000001.SZ"],
                start_date="20240102",
                end_date="20240102",  # Same
            )


# ── Param grid size validators ────────────────────────────────────────────────


class TestParamGridValidators:
    def test_too_many_keys_rejected(self):
        """BacktestSweepRequest rejects param_grid with > 10 keys."""
        from pydantic import ValidationError
        from hqmts.api.routes.backtest import BacktestSweepRequest

        grid = {f"p{i}": [1, 2] for i in range(11)}
        with pytest.raises(ValidationError, match="at most 10"):
            BacktestSweepRequest(
                strategy_name="dual_ma",
                param_grid=grid,
                instruments=["000001.SZ"],
                start_date="20240102",
                end_date="20240103",
            )

    def test_too_many_values_rejected(self):
        """BacktestSweepRequest rejects param values list > 100."""
        from pydantic import ValidationError
        from hqmts.api.routes.backtest import BacktestSweepRequest

        with pytest.raises(ValidationError, match="max is 100"):
            BacktestSweepRequest(
                strategy_name="dual_ma",
                param_grid={"fast_period": list(range(101))},
                instruments=["000001.SZ"],
                start_date="20240102",
                end_date="20240103",
            )

    def test_reasonable_grid_accepted(self):
        """BacktestSweepRequest accepts valid param_grid."""
        from hqmts.api.routes.backtest import BacktestSweepRequest

        req = BacktestSweepRequest(
            strategy_name="dual_ma",
            param_grid={"fast_period": [3, 5], "slow_period": [10, 15]},
            instruments=["000001.SZ"],
            start_date="20240102",
            end_date="20240103",
        )
        assert len(req.param_grid) == 2


# ── CYCLE_MAP and CYCLE_MINUTES_MAP consistency ───────────────────────────────


class TestCycleMaps:
    def test_cycle_map_and_minutes_map_same_keys(self):
        """CYCLE_MAP and CYCLE_MINUTES_MAP must have identical keys."""
        assert set(CYCLE_MAP.keys()) == set(CYCLE_MINUTES_MAP.keys())

    def test_valid_cycle_strings_matches_keys(self):
        """VALID_CYCLE_STRINGS must match CYCLE_MAP keys."""
        assert VALID_CYCLE_STRINGS == set(CYCLE_MAP.keys())

    def test_minutes_values_positive(self):
        """All cycle minutes must be positive integers."""
        for key, minutes in CYCLE_MINUTES_MAP.items():
            assert minutes > 0, f"Cycle {key} has non-positive minutes: {minutes}"
