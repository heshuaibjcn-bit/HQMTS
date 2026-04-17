"""Strategy template and concrete implementations (FR-STR-001/002/003)."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.order import BacktestOrder
from hqmts.backtest.registry import CYCLE_MINUTES_MAP
from hqmts.core.enums import Cycle, Side, SignalType, TargetDirection
from hqmts.core.types import DecisionSnapshotId, InstrumentId, SignalId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.signal import Signal

logger = logging.getLogger(__name__)


class StrategyTemplate(ABC):
    """Abstract base for all strategy templates (SAD 13.1).

    Follows the unified interface:
    - on_init: setup parameters, validate ranges
    - on_bar: called for each completed bar with context
    - generate_signal: produce a Signal or None
    - on_order_update: notification of order state change
    - on_trade_update: notification of a fill
    - on_stop: cleanup
    """

    @abstractmethod
    def on_init(self, params: dict) -> None:
        """Initialize strategy with parameters."""
        ...

    @abstractmethod
    def on_bar(self, bar: Bar, context: StrategyContext) -> None:
        """Called for each completed bar. Update internal state."""
        ...

    @abstractmethod
    def generate_signal(self, context: StrategyContext) -> Signal | None:
        """Produce a trading signal or None."""
        ...

    def generate_orders(self, context: StrategyContext) -> list[BacktestOrder]:
        """Produce orders for the current bar.

        Default implementation delegates to generate_signal() and wraps
        the result in a BacktestOrder. Override for richer order types,
        stop-loss, take-profit, or multi-order output.
        """
        signal = self.generate_signal(context)
        if signal is None:
            return []
        side = Side.BUY if signal.signal_type in (SignalType.OPEN_LONG, SignalType.CLOSE_SHORT) else Side.SELL
        return [BacktestOrder(
            instrument_id=str(signal.instrument_id),
            side=side,
            quantity=0,
            order_type="market",
            signal_id=str(signal.signal_id),
            reason_code=signal.reason_code or "",
        )]

    def on_order_update(self, order_state: str, context: StrategyContext) -> None:
        """Notification of order state change. Default no-op."""
        pass

    def on_trade_update(self, fill_price: Decimal, fill_quantity: int, context: StrategyContext) -> None:
        """Notification of a fill. Default no-op."""
        pass

    def on_stop(self, context: StrategyContext) -> None:
        """Cleanup. Default no-op."""
        pass


class DualMACrossoverStrategy(StrategyTemplate):
    """Dual Moving Average Crossover strategy.

    Parameters:
    - fast_period: int (default 5, range [2, 50])
    - slow_period: int (default 20, range [5, 120])

    Signal logic:
    - fast_ma crosses above slow_ma -> OPEN_LONG (golden cross)
    - fast_ma crosses below slow_ma -> CLOSE_LONG (death cross)
    - Otherwise -> no signal
    """

    def __init__(self) -> None:
        self._fast_period: int = 5
        self._slow_period: int = 20
        self._closes: list[Decimal] = []
        self._prev_fast_above: bool | None = None

    def on_init(self, params: dict) -> None:
        self._fast_period = params.get("fast_period", 5)
        self._slow_period = params.get("slow_period", 20)

        if self._fast_period >= self._slow_period:
            raise ValueError(f"fast_period ({self._fast_period}) must be < slow_period ({self._slow_period})")
        if self._fast_period < 2:
            raise ValueError(f"fast_period must be >= 2, got {self._fast_period}")
        if self._slow_period < 5:
            raise ValueError(f"slow_period must be >= 5, got {self._slow_period}")

        self._closes = []
        self._prev_fast_above = None

    def on_bar(self, bar: Bar, context: StrategyContext) -> None:
        self._closes.append(bar.close)
        # Keep only what we need
        max_keep = self._slow_period + 1
        if len(self._closes) > max_keep:
            self._closes = self._closes[-max_keep:]

    def generate_signal(self, context: StrategyContext) -> Signal | None:
        if len(self._closes) < self._slow_period:
            return None

        fast_ma = sum(self._closes[-self._fast_period:]) / Decimal(self._fast_period)
        slow_ma = sum(self._closes[-self._slow_period:]) / Decimal(self._slow_period)

        fast_above = fast_ma > slow_ma

        signal_type: SignalType | None = None
        if self._prev_fast_above is not None:
            # Golden cross: fast crosses above slow
            if fast_above and not self._prev_fast_above:
                signal_type = SignalType.OPEN_LONG
            # Death cross: fast crosses below slow
            elif not fast_above and self._prev_fast_above:
                signal_type = SignalType.CLOSE_LONG

        self._prev_fast_above = fast_above

        if signal_type is None:
            return None

        now = context.decision_time
        valid_until = now + timedelta(minutes=_cycle_to_minutes(context.cycle))

        return Signal(
            signal_id=SignalId(str(uuid.uuid4())),
            strategy_instance_id=context.strategy_instance_id,
            strategy_version=context.strategy_version,
            decision_time=now,
            instrument_id=context.instrument_id,
            signal_type=signal_type,
            target_direction=TargetDirection.LONG if signal_type == SignalType.OPEN_LONG else TargetDirection.FLAT,
            signal_strength=1.0,
            valid_until=valid_until,
            reason_code=f"dual_ma_cross_fast{self._fast_period}_slow{self._slow_period}",
            decision_snapshot_id=DecisionSnapshotId(f"bt-{now.strftime('%Y%m%d%H%M%S')}"),
            cycle=context.cycle,
            created_at=now,
        )


def _cycle_to_minutes(cycle: Cycle) -> int:
    """Convert Cycle enum to minutes."""
    return CYCLE_MINUTES_MAP[cycle.value]
