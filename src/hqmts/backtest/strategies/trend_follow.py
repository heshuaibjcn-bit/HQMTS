"""Trend Following strategy using ATR-based trailing stop.

Parameters:
- atr_period: int (default 14, range [5, 50])
- atr_multiplier: float (default 3.0, range [1.0, 10.0])

Signal logic:
- Price above trailing stop (ATR * multiplier from low) -> OPEN_LONG
- Price below trailing stop -> CLOSE_LONG
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.order import BacktestOrder
from hqmts.backtest.strategy import StrategyTemplate, _cycle_to_minutes
from hqmts.core.enums import Cycle, Side, SignalType, TargetDirection
from hqmts.core.types import DecisionSnapshotId, InstrumentId, SignalId
from hqmts.domain.bar import Bar
from hqmts.domain.signal import Signal


class TrendFollowStrategy(StrategyTemplate):
    """ATR-based trend following strategy (PRD FR-STR-001)."""

    def __init__(self) -> None:
        self._atr_period: int = 14
        self._atr_multiplier: float = 3.0
        self._highs: list[Decimal] = []
        self._lows: list[Decimal] = []
        self._closes: list[Decimal] = []
        self._trailing_stop: Decimal | None = None
        self._in_position: bool = False

    def on_init(self, params: dict) -> None:
        self._atr_period = params.get("atr_period", 14)
        self._atr_multiplier = params.get("atr_multiplier", 3.0)
        if self._atr_period < 5:
            raise ValueError(f"atr_period must be >= 5, got {self._atr_period}")
        self._highs = []
        self._lows = []
        self._closes = []
        self._trailing_stop = None
        self._in_position = False

    def on_bar(self, bar: Bar, context: StrategyContext) -> None:
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._closes.append(bar.close)
        max_keep = self._atr_period + 1
        if len(self._closes) > max_keep:
            self._highs = self._highs[-max_keep:]
            self._lows = self._lows[-max_keep:]
            self._closes = self._closes[-max_keep:]

    def generate_signal(self, context: StrategyContext) -> Signal | None:
        if len(self._closes) < self._atr_period:
            return None

        # Calculate ATR (Average True Range)
        tr_values = []
        for i in range(1, len(self._closes)):
            high = self._highs[i]
            low = self._lows[i]
            prev_close = self._closes[i - 1]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        atr = sum(tr_values[-self._atr_period:]) / Decimal(self._atr_period)
        current_close = self._closes[-1]
        current_low = self._lows[-1]

        signal_type: SignalType | None = None

        # Trailing stop = low - ATR * multiplier
        new_stop = current_low - atr * Decimal(str(self._atr_multiplier))

        if self._trailing_stop is None:
            self._trailing_stop = new_stop
        else:
            # Only move stop up, never down
            self._trailing_stop = max(self._trailing_stop, new_stop)

        if not self._in_position:
            # Entry: price above trailing stop
            if current_close > self._trailing_stop:
                signal_type = SignalType.OPEN_LONG
                self._in_position = True
        else:
            # Exit: price below trailing stop
            if current_close < self._trailing_stop:
                signal_type = SignalType.CLOSE_LONG
                self._in_position = False
                self._trailing_stop = None

        if signal_type is None:
            return None

        now = context.decision_time
        return Signal(
            signal_id=SignalId(str(uuid.uuid4())),
            strategy_instance_id=context.strategy_instance_id,
            strategy_version=context.strategy_version,
            decision_time=now,
            instrument_id=context.instrument_id,
            signal_type=signal_type,
            target_direction=TargetDirection.LONG if signal_type == SignalType.OPEN_LONG else TargetDirection.FLAT,
            signal_strength=1.0,
            valid_until=now + timedelta(minutes=_cycle_to_minutes(context.cycle)),
            reason_code=f"trend_atr{self._atr_period}_mult{self._atr_multiplier}",
            decision_snapshot_id=DecisionSnapshotId(f"bt-{now.strftime('%Y%m%d%H%M%S')}"),
            cycle=context.cycle,
            created_at=now,
        )
