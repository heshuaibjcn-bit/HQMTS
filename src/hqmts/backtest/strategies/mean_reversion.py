"""Mean Reversion strategy using Bollinger Bands.

Parameters:
- bb_period: int (default 20, range [5, 60])
- bb_std: float (default 2.0, range [1.0, 4.0])

Signal logic:
- Price below lower band -> OPEN_LONG (oversold)
- Price above upper band -> CLOSE_LONG (overbought)
"""

from __future__ import annotations

import math
import uuid
from datetime import timedelta
from decimal import Decimal

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.strategy import StrategyTemplate, _cycle_to_minutes
from hqmts.core.enums import SignalType, TargetDirection
from hqmts.core.types import DecisionSnapshotId, SignalId
from hqmts.domain.bar import Bar
from hqmts.domain.signal import Signal


class MeanReversionStrategy(StrategyTemplate):
    """Bollinger Band mean reversion strategy (PRD FR-STR-001)."""

    def __init__(self) -> None:
        self._bb_period: int = 20
        self._bb_std: float = 2.0
        self._closes: list[Decimal] = []
        self._in_position: bool = False

    def on_init(self, params: dict) -> None:
        self._bb_period = params.get("bb_period", 20)
        self._bb_std = params.get("bb_std", 2.0)
        if self._bb_period < 5:
            raise ValueError(f"bb_period must be >= 5, got {self._bb_period}")
        self._closes = []
        self._in_position = False

    def on_bar(self, bar: Bar, context: StrategyContext) -> None:
        self._closes.append(bar.close)
        if len(self._closes) > self._bb_period + 1:
            self._closes = self._closes[-(self._bb_period + 1):]

    def generate_signal(self, context: StrategyContext) -> Signal | None:
        if len(self._closes) < self._bb_period:
            return None

        recent = self._closes[-self._bb_period:]
        sma = sum(recent) / Decimal(self._bb_period)

        # Standard deviation
        variance = sum((c - sma) ** 2 for c in recent) / Decimal(self._bb_period)
        std = Decimal(str(math.sqrt(float(variance))))

        upper_band = sma + Decimal(str(self._bb_std)) * std
        lower_band = sma - Decimal(str(self._bb_std)) * std

        current_close = self._closes[-1]
        signal_type = None

        if not self._in_position:
            if current_close < lower_band:
                signal_type = SignalType.OPEN_LONG
                self._in_position = True
        else:
            if current_close > upper_band:
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
            reason_code=f"meanrev_bb{self._bb_period}_std{self._bb_std}",
            decision_snapshot_id=DecisionSnapshotId(f"bt-{now.strftime('%Y%m%d%H%M%S')}"),
            cycle=context.cycle,
            created_at=now,
        )
