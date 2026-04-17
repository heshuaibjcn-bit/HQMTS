"""BacktestRunner: async orchestrator for backtest execution and parameter sweeps."""

from __future__ import annotations

import itertools
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.backtest.engine import BacktestConfig, BacktestEngine
from hqmts.backtest.registry import CYCLE_MAP, STRATEGY_REGISTRY as _STRATEGY_REGISTRY
from hqmts.backtest.result import BacktestResult
from hqmts.backtest.strategy import StrategyTemplate
from hqmts.core.enums import Cycle
from hqmts.core.types import InstrumentId
from hqmts.domain.instrument import Instrument

logger = logging.getLogger(__name__)


@dataclass
class SweepResult:
    """Container for parameter sweep results."""
    results: list[BacktestResult]
    failed_runs: int


class BacktestRunner:
    """Async orchestrator: resolve strategy → load data → run engine → persist.

    Usage:
        runner = BacktestRunner(db_session=session)
        result = await runner.run_backtest(request)
        results = await runner.run_parameter_sweep(...)
    """

    def __init__(self, db_session: AsyncSession | None = None) -> None:
        self._db_session = db_session

    async def run_backtest(
        self,
        strategy_name: str,
        strategy_params: dict[str, Any],
        instruments: list[str],
        cycle: str,
        start_date: str,
        end_date: str,
        initial_cash: Decimal = Decimal("1000000"),
        bars_by_instrument: dict[str, list] | None = None,
    ) -> BacktestResult:
        """Run a single backtest.

        If bars_by_instrument is provided, uses those bars directly.
        Otherwise, would load from DB/Tushare (currently requires bars).
        """
        # Resolve strategy
        if strategy_name not in _STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(_STRATEGY_REGISTRY.keys())}")

        strategy_class, default_params = _STRATEGY_REGISTRY[strategy_name]
        merged_params = {**default_params, **strategy_params}

        # Build instruments
        inst_objects = [
            Instrument(
                instrument_id=InstrumentId(iid),
                ts_code=iid,
                exchange="SZSE",
                symbol=iid.split(".")[0],
                name=iid,
            )
            for iid in instruments
        ]

        # Cycle mapping
        resolved_cycle = CYCLE_MAP.get(cycle, Cycle.M5)

        # Run engine
        config = BacktestConfig(
            strategy=strategy_class(),
            strategy_name=strategy_name,
            strategy_version="v1",
            strategy_params=merged_params,
            instruments=inst_objects,
            cycle=resolved_cycle,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
        )

        engine = BacktestEngine(config)
        bars = bars_by_instrument or {}
        if not bars:
            raise ValueError("No bar data provided. Supply bars_by_instrument for the target instruments.")
        result = engine.run(bars)

        # Persist if session available
        if self._db_session is not None:
            try:
                from hqmts.db.repositories.backtest_repo import BacktestResultRepository
                repo = BacktestResultRepository(self._db_session)
                await repo.save(result)
                await self._db_session.commit()
            except Exception:
                if self._db_session:
                    await self._db_session.rollback()
                logger.warning("Failed to persist backtest result", exc_info=True)

        return result

    async def run_parameter_sweep(
        self,
        strategy_name: str,
        param_grid: dict[str, list[Any]],
        instruments: list[str],
        cycle: str,
        start_date: str,
        end_date: str,
        initial_cash: Decimal = Decimal("1000000"),
        bars_by_instrument: dict[str, list] | None = None,
    ) -> SweepResult:
        """Run backtests for every parameter combination in the grid.

        Returns SweepResult with results sorted by total_return descending.
        """
        if strategy_name not in _STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(_STRATEGY_REGISTRY.keys())}")

        _, default_params = _STRATEGY_REGISTRY[strategy_name]

        # Enumerate all parameter combinations with size cap
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))

        MAX_COMBINATIONS = 10000
        if len(combinations) > MAX_COMBINATIONS:
            raise ValueError(
                f"Parameter grid produces {len(combinations)} combinations, "
                f"exceeding limit of {MAX_COMBINATIONS}. Reduce grid size."
            )

        results: list[BacktestResult] = []
        errors: list[str] = []
        for combo in combinations:
            combo_params = dict(zip(param_names, combo))
            merged = {**default_params, **combo_params}

            try:
                result = await self.run_backtest(
                    strategy_name=strategy_name,
                    strategy_params=merged,
                    instruments=instruments,
                    cycle=cycle,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    bars_by_instrument=bars_by_instrument,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"params={combo_params}: {e}")
                logger.warning("Parameter sweep failed for params=%s: %s", combo_params, e)

        if not results and errors:
            raise RuntimeError(
                f"All {len(errors)} parameter combinations failed. "
                f"First error: {errors[0]}"
            )

        # Sort by total_return descending
        results.sort(key=lambda r: r.total_return, reverse=True)
        return SweepResult(results=results, failed_runs=len(errors))
