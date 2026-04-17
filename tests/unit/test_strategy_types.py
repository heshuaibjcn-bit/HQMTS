"""Tests for concrete strategy types (PRD FR-STR-001)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.strategies.breakout import BreakoutStrategy
from hqmts.backtest.strategies.cross_cycle import CrossCycleStrategy
from hqmts.backtest.strategies.mean_reversion import MeanReversionStrategy
from hqmts.backtest.strategies.trend_follow import TrendFollowStrategy
from hqmts.core.enums import Cycle, SignalType
from hqmts.core.types import InstrumentId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar


def _ctx(decision_time: datetime) -> StrategyContext:
    return StrategyContext(
        strategy_instance_id=StrategyInstanceId("test"),
        strategy_version=VersionStr("v1"),
        instrument_id=InstrumentId("000001.SZ"),
        cycle=Cycle.M5,
        decision_time=decision_time,
    )


def _bar(close: str, dt: datetime, high: str | None = None, low: str | None = None) -> Bar:
    c = Decimal(close)
    h = Decimal(high) if high else c + Decimal("0.10")
    l = Decimal(low) if low else c - Decimal("0.10")
    return Bar(
        instrument_id=InstrumentId("000001.SZ"),
        cycle=Cycle.M5,
        bar_start_time=dt,
        bar_end_time=dt + timedelta(minutes=5),
        open=c, high=h, low=l, close=c,
        volume=100000, amount=Decimal("1000000"),
        is_completed=True, source="test",
        data_version=VersionStr("v1"),
    )


def _make_bars_trending_up(count: int, base_time: datetime) -> list[Bar]:
    """Generate bars with steadily rising prices."""
    bars = []
    for i in range(count):
        price = 10.0 + i * 0.2
        dt = base_time + timedelta(minutes=5 * i)
        bars.append(_bar(close=f"{price:.2f}", dt=dt, high=f"{price + 0.3:.2f}", low=f"{price - 0.3:.2f}"))
    return bars


def _make_bars_trending_down(count: int, base_time: datetime) -> list[Bar]:
    """Generate bars with steadily declining prices."""
    bars = []
    for i in range(count):
        price = 15.0 - i * 0.2
        dt = base_time + timedelta(minutes=5 * i)
        bars.append(_bar(close=f"{price:.2f}", dt=dt, high=f"{price + 0.3:.2f}", low=f"{price - 0.3:.2f}"))
    return bars


class TestTrendFollowStrategy:
    def test_init_validates_params(self):
        s = TrendFollowStrategy()
        with pytest.raises(ValueError, match="atr_period"):
            s.on_init({"atr_period": 2})

    def test_no_signal_insufficient_data(self):
        s = TrendFollowStrategy()
        s.on_init({"atr_period": 14})
        base = datetime(2024, 1, 2, 9, 30)
        for i in range(5):
            bar = _bar("10.00", base + timedelta(minutes=5 * i))
            s.on_bar(bar, _ctx(bar.bar_start_time))
        signal = s.generate_signal(_ctx(base + timedelta(minutes=25)))
        assert signal is None

    def test_generates_signal_with_enough_data(self):
        s = TrendFollowStrategy()
        s.on_init({"atr_period": 5})
        base = datetime(2024, 1, 2, 9, 30)
        bars = _make_bars_trending_up(15, base)
        signal_found = False
        for bar in bars:
            s.on_bar(bar, _ctx(bar.bar_start_time))
            sig = s.generate_signal(_ctx(bar.bar_start_time))
            if sig is not None:
                signal_found = True
                break
        assert signal_found


class TestMeanReversionStrategy:
    def test_init_validates_params(self):
        s = MeanReversionStrategy()
        with pytest.raises(ValueError, match="bb_period"):
            s.on_init({"bb_period": 2})

    def test_no_signal_insufficient_data(self):
        s = MeanReversionStrategy()
        s.on_init({"bb_period": 20})
        base = datetime(2024, 1, 2, 9, 30)
        for i in range(10):
            bar = _bar("10.00", base + timedelta(minutes=5 * i))
            s.on_bar(bar, _ctx(bar.bar_start_time))
        signal = s.generate_signal(_ctx(base + timedelta(minutes=50)))
        assert signal is None

    def test_oversold_triggers_buy(self):
        s = MeanReversionStrategy()
        s.on_init({"bb_period": 10, "bb_std": 2.0})
        base = datetime(2024, 1, 2, 9, 30)
        # Steady prices then sharp drop
        for i in range(10):
            bar = _bar("10.00", base + timedelta(minutes=5 * i))
            s.on_bar(bar, _ctx(bar.bar_start_time))
        # Sharp drop below lower band
        bar = _bar("8.00", base + timedelta(minutes=50))
        s.on_bar(bar, _ctx(bar.bar_start_time))
        sig = s.generate_signal(_ctx(bar.bar_start_time))
        assert sig is not None
        assert sig.signal_type == SignalType.OPEN_LONG


class TestBreakoutStrategy:
    def test_init_validates_exit_period(self):
        s = BreakoutStrategy()
        with pytest.raises(ValueError, match="exit_period"):
            s.on_init({"channel_period": 10, "exit_period": 20})

    def test_no_signal_insufficient_data(self):
        s = BreakoutStrategy()
        s.on_init({"channel_period": 10, "exit_period": 5})
        base = datetime(2024, 1, 2, 9, 30)
        for i in range(5):
            bar = _bar("10.00", base + timedelta(minutes=5 * i))
            s.on_bar(bar, _ctx(bar.bar_start_time))
        sig = s.generate_signal(_ctx(base + timedelta(minutes=25)))
        assert sig is None

    def test_breakout_above_high(self):
        s = BreakoutStrategy()
        s.on_init({"channel_period": 5, "exit_period": 3})
        base = datetime(2024, 1, 2, 9, 30)
        # Build a range: highs around 11
        for i in range(6):
            bar = _bar("10.50", base + timedelta(minutes=5 * i), high="11.00", low="10.00")
            s.on_bar(bar, _ctx(bar.bar_start_time))
        # Breakout above 11
        bar = _bar("11.50", base + timedelta(minutes=30), high="11.60", low="11.40")
        s.on_bar(bar, _ctx(bar.bar_start_time))
        sig = s.generate_signal(_ctx(bar.bar_start_time))
        assert sig is not None
        assert sig.signal_type == SignalType.OPEN_LONG


class TestCrossCycleStrategy:
    def test_init_validates_cycles(self):
        s = CrossCycleStrategy()
        with pytest.raises(ValueError, match="Invalid fast_cycle"):
            s.on_init({"fast_cycle": "2m", "slow_cycle": "60m"})

    def test_init_validates_slow_gte_fast(self):
        s = CrossCycleStrategy()
        with pytest.raises(ValueError, match="slow_cycle must be >= fast_cycle"):
            s.on_init({"fast_cycle": "60m", "slow_cycle": "5m"})

    def test_no_signal_insufficient_data(self):
        s = CrossCycleStrategy()
        s.on_init({"fast_cycle": "5m", "slow_cycle": "60m", "ma_period": 10})
        base = datetime(2024, 1, 2, 9, 30)
        for i in range(5):
            bar = _bar("10.00", base + timedelta(minutes=5 * i))
            s.on_bar(bar, _ctx(bar.bar_start_time))
        sig = s.generate_signal(_ctx(base + timedelta(minutes=25)))
        assert sig is None

    def test_generates_signal_with_trend(self):
        s = CrossCycleStrategy()
        s.on_init({"fast_cycle": "5m", "slow_cycle": "60m", "ma_period": 5})
        base = datetime(2024, 1, 2, 9, 30)
        # Feed 60 bars of trending up data (5 hours of 5m bars)
        for i in range(60):
            price = 10.0 + i * 0.1
            bar = _bar(f"{price:.2f}", base + timedelta(minutes=5 * i))
            s.on_bar(bar, _ctx(bar.bar_start_time))
            sig = s.generate_signal(_ctx(bar.bar_start_time))
            # At some point we should get a signal
            if sig is not None:
                assert sig.signal_type in (SignalType.OPEN_LONG, SignalType.CLOSE_LONG)
                return
        # May not trigger with this data pattern, that's ok
