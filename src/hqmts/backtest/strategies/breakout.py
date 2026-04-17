"""Breakout strategy using Donchian Channel.

Parameters:
- channel_period: int (default 20, range [5, 60])
- exit_period: int (default 10, range [3, 30])

Signal logic:
- Price above highest high of period -> OPEN_LONG (breakout up)
- Price below lowest low of exit_period -> CLOSE_LONG
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.strategy import StrategyTemplate, _cycle_to_minutes
from hqmts.core.enums import SignalType, TargetDirection
from hqmts.core.types import DecisionSnapshotId, SignalId
from hqmts.domain.bar import Bar
from hqmts.domain.signal import Signal


class BreakoutStrategy(StrategyTemplate):
    """Donchian Channel breakout strategy (PRD FR-STR-001)."""

    def __init__(self) -> None:
        self._channel_period: int = 20
        self._exit_period: int = 10
        self._highs: list[Decimal] = []
        self._lows: list[Decimal] = []
        self._closes: list[Decimal] = []
        self._in_position: bool = False

    def on_init(self, params: dict) -> None:
        self._channel_period = params.get("channel_period", 20)
        self._exit_period = params.get("exit_period", 10)
        if self._exit_period > self._channel_period:
            raise ValueError(f"exit_period ({self._exit_period}) must be <= channel_period ({self._channel_period})")
        self._highs = []
        self._lows = []
        self._closes = []
        self._in_position = False

    def on_bar(self, bar: Bar, context: StrategyContext) -> None:
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._closes.append(bar.close)
        max_keep = self._channel_period + 1
        if len(self._closes) > max_keep:
            self._highs = self._highs[-max_keep:]
            self._lows = self._lows[-max_keep:]
            self._closes = self._closes[-max_keep:]

    def generate_signal(self, context: StrategyContext) -> Signal | None:
        if len(self._closes) < self._channel_period:
            return None

        current_close = self._closes[-1]

        # Entry: highest high of channel_period (excluding current bar)
        highest_high = max(self._highs[-self._channel_period:-1]) if len(self._highs) > self._channel_period else max(self._highs[:-1])

        # Exit: lowest low of exit_period (excluding current bar)
        exit_lows = self._lows[-self._exit_period:-1] if len(self._lows) > self._exit_period else self._lows[:-1]
        lowest_low = min(exit_lows) if exit_lows else self._lows[-1]

        signal_type = None

        if not self._in_position:
            if current_close > highest_high:
                signal_type = SignalType.OPEN_LONG
                self._in_position = True
        else:
            if current_close < lowest_low:
                signal_type = SignalType.CLOSE_LONG
                self._in_position = False

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
            reason_code=f"breakout_dc{self._channel_period}_exit{self._exit_period}",
            decision_snapshot_id=DecisionSnapshotId(f"bt-{now.strftime('%Y%m%d%H%M%S')}"),
            cycle=context.cycle,
            created_at=now,
        )
