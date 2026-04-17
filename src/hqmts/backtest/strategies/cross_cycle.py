"""Cross-Cycle strategy: uses multiple timeframes for confirmation.

Parameters:
- fast_cycle: str (default "5m") — signal cycle
- slow_cycle: str (default "60m") — trend filter cycle
- ma_period: int (default 10) — MA period for both cycles

Signal logic:
- Slow cycle MA rising (uptrend) AND fast cycle golden cross -> OPEN_LONG
- Fast cycle death cross -> CLOSE_LONG
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.strategy import StrategyTemplate, _cycle_to_minutes
from hqmts.core.enums import Cycle, SignalType, TargetDirection
from hqmts.core.types import DecisionSnapshotId, SignalId
from hqmts.domain.bar import Bar
from hqmts.domain.signal import Signal

CYCLE_MAP_STR = {"1m": Cycle.M1, "5m": Cycle.M5, "15m": Cycle.M15, "30m": Cycle.M30, "60m": Cycle.M60}


class CrossCycleStrategy(StrategyTemplate):
    """Multi-timeframe cross-cycle strategy (PRD FR-STR-001).

    Maintains separate close buffers for fast and slow cycles.
    In backtest, uses bar-level closes and simulates multi-cycle by
    sampling at cycle boundaries.
    """

    def __init__(self) -> None:
        self._fast_cycle: str = "5m"
        self._slow_cycle: str = "60m"
        self._ma_period: int = 10
        self._fast_closes: list[Decimal] = []
        self._slow_closes: list[Decimal] = []
        self._slow_ma_rising: bool = False
        self._prev_fast_above: bool | None = None
        self._in_position: bool = False
        self._bar_count: int = 0
        self._bars_per_slow: int = 12  # 60m / 5m = 12

    def on_init(self, params: dict) -> None:
        self._fast_cycle = params.get("fast_cycle", "5m")
        self._slow_cycle = params.get("slow_cycle", "60m")
        self._ma_period = params.get("ma_period", 10)
        if self._fast_cycle not in CYCLE_MAP_STR:
            raise ValueError(f"Invalid fast_cycle: {self._fast_cycle}")
        if self._slow_cycle not in CYCLE_MAP_STR:
            raise ValueError(f"Invalid slow_cycle: {self._slow_cycle}")
        # Calculate bars per slow cycle
        fast_min = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}
        slow_min = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}
        ratio = slow_min[self._slow_cycle] / fast_min[self._fast_cycle]
        if ratio < 1:
            raise ValueError(f"slow_cycle must be >= fast_cycle, got {self._slow_cycle} < {self._fast_cycle}")
        self._bars_per_slow = int(ratio)
        self._fast_closes = []
        self._slow_closes = []
        self._slow_ma_rising = False
        self._prev_fast_above = None
        self._in_position = False
        self._bar_count = 0

    def on_bar(self, bar: Bar, context: StrategyContext) -> None:
        self._bar_count += 1
        self._fast_closes.append(bar.close)
        if len(self._fast_closes) > self._ma_period + 1:
            self._fast_closes = self._fast_closes[-(self._ma_period + 1):]

        # At slow cycle boundary, sample a close for the slow MA
        if self._bar_count % self._bars_per_slow == 0:
            self._slow_closes.append(bar.close)
            if len(self._slow_closes) > self._ma_period + 1:
                self._slow_closes = self._slow_closes[-(self._ma_period + 1):]

            # Update slow trend
            if len(self._slow_closes) >= self._ma_period:
                slow_ma = sum(self._slow_closes[-self._ma_period:]) / Decimal(self._ma_period)
                if len(self._slow_closes) > self._ma_period:
                    prev_slow_ma = sum(self._slow_closes[-self._ma_period - 1:-1]) / Decimal(self._ma_period)
                    self._slow_ma_rising = slow_ma > prev_slow_ma

    def generate_signal(self, context: StrategyContext) -> Signal | None:
        if len(self._fast_closes) < self._ma_period:
            return None

        fast_ma = sum(self._fast_closes[-self._ma_period:]) / Decimal(self._ma_period)
        current_close = self._fast_closes[-1]
        fast_above = current_close > fast_ma

        signal_type = None

        if self._prev_fast_above is not None:
            golden_cross = fast_above and not self._prev_fast_above
            death_cross = not fast_above and self._prev_fast_above

            if not self._in_position:
                if golden_cross and self._slow_ma_rising:
                    signal_type = SignalType.OPEN_LONG
                    self._in_position = True
            else:
                if death_cross:
                    signal_type = SignalType.CLOSE_LONG
                    self._in_position = False

        self._prev_fast_above = fast_above

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
            reason_code=f"crosscycle_{self._fast_cycle}_{self._slow_cycle}_ma{self._ma_period}",
            decision_snapshot_id=DecisionSnapshotId(f"bt-{now.strftime('%Y%m%d%H%M%S')}"),
            cycle=context.cycle,
            created_at=now,
        )
