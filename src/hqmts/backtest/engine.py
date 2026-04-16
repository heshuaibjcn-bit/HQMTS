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
from hqmts.backtest.order import BacktestOrder
from hqmts.backtest.portfolio import PortfolioState
from hqmts.backtest.result import BacktestResult, BacktestResultBuilder
from hqmts.backtest.risk_adapter import SyncRiskAdapter, build_risk_context
from hqmts.backtest.strategy import StrategyTemplate
from hqmts.core.enums import Cycle, RiskResultType, Side, SignalType
from hqmts.core.types import InstrumentId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument
from hqmts.domain.signal import Signal
from hqmts.risk.engine import RiskEngine

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
    risk_engine: RiskEngine | None = None
    enable_risk: bool = False


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
        # Risk adapter: disabled unless enable_risk=True
        if config.enable_risk and config.risk_engine is not None:
            self._risk_adapter = SyncRiskAdapter(config.risk_engine)
        else:
            self._risk_adapter = SyncRiskAdapter(None)

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
        orders_buffer: list[tuple[BacktestOrder, int]] = []  # (order, delay_count)
        MAX_DELAY_ATTEMPTS = 3

        try:
            for bar in all_bars:
                iid = str(bar.instrument_id)
                trade_date = bar.bar_start_time.date()

                # Day change: reset T+1 state, snapshot previous day
                if trade_date != prev_trade_date:
                    if prev_trade_date is not None:
                        self._portfolio.update_market_value_from_prices(self._latest_prices)
                        self._portfolio.snapshot_daily(prev_trade_date)
                    self._portfolio.reset_daily_state()
                    prev_trade_date = trade_date

                # Update incremental price map
                self._latest_prices[iid] = bar.close

                # Check stop-loss / take-profit triggers before processing new signals
                if bar.is_completed:
                    sl_triggered = self._portfolio.check_stop_loss_triggers(self._latest_prices)
                    tp_triggered = self._portfolio.check_take_profit_triggers(self._latest_prices)
                    for sl_iid in sl_triggered:
                        self._process_sl_tp(sl_iid, Side.SELL, bar, inst_map.get(sl_iid))
                    for tp_iid in tp_triggered:
                        self._process_sl_tp(tp_iid, Side.SELL, bar, inst_map.get(tp_iid))

                # Update prev_close
                if iid not in self._prev_close:
                    self._prev_close[iid] = bar.close
                    continue  # First bar per instrument: warmup, seed baseline. No signal generated.

                # Feed bar to strategy (only for matching instruments)
                if iid in inst_map:
                    ctx = self._build_context(iid, bar)
                    config.strategy.on_bar(bar, ctx)
                    orders = config.strategy.generate_orders(ctx)

                    for order in orders:
                        if order.stop_loss is not None or order.take_profit is not None:
                            self._portfolio.update_stop_loss_take_profit(
                                order.instrument_id, order.stop_loss, order.take_profit,
                            )
                        orders_buffer.append((order, 0))

                # Process orders from previous bars against this bar
                remaining: list[tuple[BacktestOrder, int]] = []
                for order, delay_count in orders_buffer:
                    if order.instrument_id == iid and bar.is_completed:
                        result = self._process_order(order, bar, inst_map.get(order.instrument_id))
                        if result == "delayed" and delay_count < MAX_DELAY_ATTEMPTS:
                            remaining.append((order, delay_count + 1))
                            logger.debug("Re-queuing delayed order=%s attempt=%d", order.signal_id, delay_count + 1)
                    else:
                        remaining.append((order, delay_count))
                orders_buffer = remaining

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
        finally:
            self._risk_adapter.close()

    def _process_order(
        self,
        order: BacktestOrder,
        target_bar: Bar,
        instrument: Instrument | None,
    ) -> str:
        """Try to match a BacktestOrder against a target bar and update portfolio.

        Returns: "filled", "delayed", "rejected", or "skipped".
        """
        if instrument is None:
            return "skipped"

        iid = order.instrument_id
        pos = self._portfolio.get_or_create_position(iid)
        prev_close = self._prev_close.get(iid, target_bar.open)

        # Risk check (if enabled)
        if self._config.enable_risk:
            risk_ctx = build_risk_context(order, self._portfolio, iid)
            risk_result = self._risk_adapter.evaluate(risk_ctx)

            if risk_result.result_type == RiskResultType.REJECT:
                logger.debug("Risk rejected: order=%s reason=%s", order.signal_id, risk_result.reject_reason)
                return "rejected"
            elif risk_result.result_type == RiskResultType.RESIZE:
                if risk_result.resized_quantity is not None:
                    order = BacktestOrder(
                        instrument_id=order.instrument_id,
                        side=order.side,
                        quantity=risk_result.resized_quantity,
                        order_type=order.order_type,
                        limit_price=order.limit_price,
                        stop_loss=order.stop_loss,
                        take_profit=order.take_profit,
                        signal_id=order.signal_id,
                        reason_code=order.reason_code,
                    )
                # If resized_quantity is None, proceed with original quantity
            elif risk_result.result_type == RiskResultType.DELAY:
                logger.debug("Risk delayed: order=%s", order.signal_id)
                return "delayed"
            elif risk_result.result_type == RiskResultType.FORCE_FLATTEN:
                logger.debug("Risk force_flatten: closing all positions")
                self._force_flatten_all(target_bar, inst_map=None)
                return "filled"

        result = self._matcher.match_order_from_bt(
            order=order,
            target_bar=target_bar,
            prev_close=prev_close,
            instrument=instrument,
            current_position=pos.quantity,
            today_bought=pos.today_bought,
            available_cash=self._portfolio.cash,
        )

        if result.filled:
            self._portfolio.apply_fill(
                instrument_id=iid,
                side=order.side,
                fill_price=result.fill_price,
                fill_quantity=result.fill_quantity,
                commission=result.commission,
                stamp_tax=result.stamp_tax,
                timestamp=target_bar.bar_start_time,
                signal_id=order.signal_id,
            )
            logger.debug(
                "Fill: %s %s %d@%s (order=%s)",
                order.side.value, iid, result.fill_quantity, result.fill_price, order.signal_id,
            )
            return "filled"
        else:
            logger.debug(
                "Rejected: order=%s reason=%s",
                order.signal_id, result.reject_reason,
            )
            return "rejected"

    def _process_sl_tp(
        self,
        instrument_id: str,
        side: Side,
        target_bar: Bar,
        instrument: Instrument | None,
    ) -> None:
        """Process a stop-loss or take-profit trigger."""
        if instrument is None:
            return

        pos = self._portfolio.get_or_create_position(instrument_id)
        if pos.quantity <= 0:
            return

        prev_close = self._prev_close.get(instrument_id, target_bar.open)

        # Build a sell order for all sellable shares
        order = BacktestOrder(
            instrument_id=instrument_id,
            side=Side.SELL,
            quantity=0,  # all available
            order_type="market",
            signal_id=f"sl-tp-{instrument_id}",
            reason_code="stop_loss_take_profit",
        )

        result = self._matcher.match_order_from_bt(
            order=order,
            target_bar=target_bar,
            prev_close=prev_close,
            instrument=instrument,
            current_position=pos.quantity,
            today_bought=pos.today_bought,
            available_cash=self._portfolio.cash,
        )

        if result.filled:
            self._portfolio.apply_fill(
                instrument_id=instrument_id,
                side=Side.SELL,
                fill_price=result.fill_price,
                fill_quantity=result.fill_quantity,
                commission=result.commission,
                stamp_tax=result.stamp_tax,
                timestamp=target_bar.bar_start_time,
                signal_id=order.signal_id,
            )
            # Clear SL/TP after trigger
            pos.stop_loss = None
            pos.take_profit = None
            logger.debug("SL/TP trigger: sell %s %d@%s", instrument_id, result.fill_quantity, result.fill_price)

    def _force_flatten_all(self, target_bar: Bar, inst_map: dict[str, Instrument] | None = None) -> None:
        """Force-sell all positions (triggered by FORCE_FLATTEN risk result)."""
        for iid, pos in list(self._portfolio.positions.items()):
            if pos.quantity <= 0:
                continue
            instrument = None
            if inst_map:
                instrument = inst_map.get(iid)
            if instrument is None:
                # Try to find from config instruments
                for inst in self._config.instruments:
                    if str(inst.instrument_id) == iid:
                        instrument = inst
                        break
            if instrument is None:
                continue
            self._process_sl_tp(iid, Side.SELL, target_bar, instrument)

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
