"""Backtest engine orchestrator (FR-BT-004)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Sequence

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.cost import CostModel, PriceLimitRule
from hqmts.backtest.matcher import BacktestMatcher, MatchResult
from hqmts.backtest.portfolio import PortfolioState
from hqmts.backtest.result import BacktestResult, BacktestResultBuilder
from hqmts.backtest.strategy import StrategyTemplate
from hqmts.core.enums import Cycle, Side, SignalType
from hqmts.core.types import InstrumentId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument
from hqmts.domain.signal import Signal

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    strategy: StrategyTemplate
    strategy_name: str
    strategy_version: str
    strategy_params: dict[str, Any]
    instruments: list[Instrument]
    cycle: Cycle
    start_date: str  # YYYYMMDD
    end_date: str  # YYYYMMDD
    initial_cash: Decimal = Decimal("1000000")
    commission_rate: Decimal = Decimal("0.0003")
    commission_min: Decimal = Decimal("5")
    stamp_tax_rate: Decimal = Decimal("0.001")
    slippage: Decimal = Decimal("0")
    lot_size: int = 100
    participation_rate: float = 0.25
    reject_on_bad_data: bool = True  # Refuse to run on FAIL-grade bar data


class BacktestEngine:
    """Orchestrates a backtest run.

    Core loop:
    1. Load bar data (provided externally)
    2. Merge all instruments' bars into chronological stream
    3. For each bar:
       a. Feed bar to strategy via on_bar()
       b. Call generate_signal()
       c. If signal, match order via BacktestMatcher
       d. If filled, update portfolio via apply_fill()
    4. Track daily snapshots
    5. Calculate final metrics via BacktestResultBuilder
    """

    def __init__(self, config: BacktestConfig) -> None:
        self._config = config
        self._cost_model = CostModel(
            commission_rate=config.commission_rate,
            commission_min=config.commission_min,
            stamp_tax_rate=config.stamp_tax_rate,
            slippage=config.slippage,
        )
        self._price_limit = PriceLimitRule()
        self._matcher = BacktestMatcher(
            cost_model=self._cost_model,
            price_limit_rule=self._price_limit,
            lot_size=config.lot_size,
            participation_rate=config.participation_rate,
        )
        self._portfolio = PortfolioState(
            cash=config.initial_cash,
            initial_cash=config.initial_cash,
        )
        self._prev_close: dict[str, Decimal] = {}
        self._latest_prices: dict[str, Decimal] = {}  # Incremental price map

    def run(self, bars_by_instrument: dict[str, list[Bar]]) -> BacktestResult:
        """Run backtest with provided bar data.

        Args:
            bars_by_instrument: dict mapping instrument_id to list of Bar objects.
                Bars should be for the configured cycle and date range.

        Returns:
            BacktestResult with all performance metrics.
        """
        config = self._config

        # Initialize strategy
        config.strategy.on_init(config.strategy_params)

        # Build instrument lookup
        inst_map: dict[str, Instrument] = {
            str(i.instrument_id): i for i in config.instruments
        }

        # Merge all bars into chronological stream
        all_bars: list[Bar] = []
        for bars in bars_by_instrument.values():
            all_bars.extend(bars)
        all_bars.sort(key=lambda b: b.bar_start_time)

        if not all_bars:
            logger.warning("No bars provided for backtest")
            return self._empty_result()

        # Data quality gate: check for zero prices (most common quality failure)
        if config.reject_on_bad_data:
            zero_price_bars = [b for b in all_bars if b.open == 0 or b.high == 0 or b.low == 0 or b.close == 0]
            if zero_price_bars:
                logger.error(
                    "Data quality gate: %d bars with zero prices, refusing to run. "
                    "Set reject_on_bad_data=False to override.",
                    len(zero_price_bars),
                )
                return self._empty_result()

        # Track prev_close per instrument
        # Group bars by date for daily reset
        prev_trade_date: date | None = None
        signals_buffer: list[Signal] = []

        for bar in all_bars:
            iid = str(bar.instrument_id)
            trade_date = bar.bar_start_time.date()

            # Day change: reset T+1 state, snapshot previous day
            if trade_date != prev_trade_date:
                if prev_trade_date is not None:
                    # Use incremental price map (O(1) per instrument) instead of scanning all_bars
                    self._portfolio.update_market_value_from_prices(self._latest_prices)
                    self._portfolio.snapshot_daily(prev_trade_date)
                self._portfolio.reset_daily_state()
                prev_trade_date = trade_date

            # Update incremental price map
            self._latest_prices[iid] = bar.close

            # Update prev_close
            if iid not in self._prev_close:
                self._prev_close[iid] = bar.close
                continue  # First bar per instrument: warmup, seed baseline. No signal generated.

            # Feed bar to strategy (only for matching instruments)
            if iid in inst_map:
                ctx = self._build_context(iid, bar)
                config.strategy.on_bar(bar, ctx)
                signal = config.strategy.generate_signal(ctx)

                if signal is not None:
                    signals_buffer.append(signal)

            # Process signals from previous bars against this bar
            remaining: list[Signal] = []
            for sig in signals_buffer:
                sig_iid = str(sig.instrument_id)
                if sig_iid == iid and bar.is_completed:
                    self._process_signal(sig, bar, inst_map.get(sig_iid))
                else:
                    remaining.append(sig)
            signals_buffer = remaining

            # Update prev_close at end of bar
            self._prev_close[iid] = bar.close

        # Final daily snapshot
        if prev_trade_date is not None:
            self._portfolio.snapshot_daily(prev_trade_date)

        # Build result
        return BacktestResultBuilder.build(
            strategy_name=config.strategy_name,
            strategy_version=config.strategy_version,
            strategy_params=config.strategy_params,
            instruments=[str(i.instrument_id) for i in config.instruments],
            cycle=config.cycle.value,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_cash=config.initial_cash,
            daily_values=self._portfolio.daily_values,
            trades=self._portfolio.trades,
        )

    def _process_signal(
        self,
        signal: Signal,
        target_bar: Bar,
        instrument: Instrument | None,
    ) -> None:
        """Try to match a signal against a target bar and update portfolio."""
        if instrument is None:
            return

        iid = str(signal.instrument_id)
        pos = self._portfolio.get_or_create_position(iid)
        prev_close = self._prev_close.get(iid, target_bar.open)

        result = self._matcher.match_order(
            signal=signal,
            target_bar=target_bar,
            prev_close=prev_close,
            instrument=instrument,
            current_position=pos.quantity,
            today_bought=pos.today_bought,
            available_cash=self._portfolio.cash,
        )

        if result.filled:
            side = Side.BUY if signal.signal_type in (SignalType.OPEN_LONG, SignalType.CLOSE_SHORT) else Side.SELL
            self._portfolio.apply_fill(
                instrument_id=iid,
                side=side,
                fill_price=result.fill_price,
                fill_quantity=result.fill_quantity,
                commission=result.commission,
                stamp_tax=result.stamp_tax,
                timestamp=target_bar.bar_start_time,
                signal_id=signal.signal_id,
            )
            logger.debug(
                "Fill: %s %s %d@%s (signal=%s)",
                side.value, iid, result.fill_quantity, result.fill_price, signal.signal_id,
            )
        else:
            logger.debug(
                "Rejected: signal=%s reason=%s",
                signal.signal_id, result.reject_reason,
            )

    def _build_context(self, instrument_id: str, bar: Bar) -> StrategyContext:
        """Build strategy context for current state."""
        pos = self._portfolio.get_or_create_position(instrument_id)
        return StrategyContext(
            strategy_instance_id=StrategyInstanceId("backtest"),
            strategy_version=VersionStr(self._config.strategy_version),
            instrument_id=InstrumentId(instrument_id),
            cycle=self._config.cycle,
            decision_time=bar.bar_start_time,
            current_position=pos.quantity,
            available_cash=self._portfolio.cash,
            total_asset=self._portfolio.calculate_total_asset(),
        )

    def _empty_result(self) -> BacktestResult:
        """Return an empty result when no bars are provided."""
        return BacktestResult(
            backtest_id="empty",
            strategy_name=self._config.strategy_name,
            strategy_version=self._config.strategy_version,
            strategy_params=self._config.strategy_params,
            instruments=[str(i.instrument_id) for i in self._config.instruments],
            cycle=self._config.cycle.value,
            start_date=self._config.start_date,
            end_date=self._config.end_date,
            initial_cash=self._config.initial_cash,
            final_total_asset=self._config.initial_cash,
            total_return=Decimal("0"),
            annualized_return=Decimal("0"),
            max_drawdown=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            total_trades=0,
            win_rate=Decimal("0"),
            profit_factor=Decimal("0"),
            trades=[],
            daily_values=[],
            cost_summary={},
        )
