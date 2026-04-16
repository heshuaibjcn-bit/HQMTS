"""Tests for strategy runtime, cost model, and matching engine."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.cost import CostModel, PriceLimitRule
from hqmts.backtest.matcher import BacktestMatcher, MatchResult
from hqmts.backtest.strategy import DualMACrossoverStrategy
from hqmts.core.enums import Cycle, Side, SignalType, TargetDirection
from hqmts.core.types import InstrumentId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument
from hqmts.domain.signal import Signal


# ── Helpers ──────────────────────────────────────────────────────────────────


def _bar(
    start: datetime,
    close: str = "10.00",
    open_: str = "10.00",
    high: str = "10.50",
    low: str = "9.50",
    volume: int = 10000,
    cycle: Cycle = Cycle.M5,
) -> Bar:
    return Bar(
        instrument_id=InstrumentId("000001.SZ"),
        cycle=cycle,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes={Cycle.M1: 1, Cycle.M5: 5, Cycle.M15: 15, Cycle.M30: 30, Cycle.M60: 60}[cycle]),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        amount=Decimal("100000"),
        is_completed=True,
        source="tushare",
        data_version=VersionStr("v1"),
    )


def _instrument(is_st: bool = False, board_type: str = "main") -> Instrument:
    return Instrument(
        instrument_id=InstrumentId("000001.SZ"),
        ts_code="000001.SZ",
        exchange="SZSE",
        symbol="000001",
        name="TestStock",
        is_st=is_st,
        board_type=board_type,
    )


def _ctx(
    position: int = 0,
    cash: str = "1000000",
    today_bought: int = 0,
    decision_time: datetime | None = None,
) -> StrategyContext:
    return StrategyContext(
        strategy_instance_id=StrategyInstanceId("test-strat"),
        strategy_version=VersionStr("v1"),
        instrument_id=InstrumentId("000001.SZ"),
        cycle=Cycle.M5,
        decision_time=decision_time or datetime(2024, 1, 2, 9, 35),
        current_position=position,
        available_cash=Decimal(cash),
        total_asset=Decimal(cash),
    )


# ── DualMACrossoverStrategy Tests ────────────────────────────────────────────


class TestDualMACrossoverStrategy:
    def test_golden_cross_generates_open_long(self):
        strat = DualMACrossoverStrategy()
        strat.on_init({"fast_period": 3, "slow_period": 5})

        # Feed bars: declining then rising to create golden cross
        closes = ["10.00", "9.80", "9.60", "9.50", "9.70", "9.80", "10.00", "10.20", "10.30"]
        ctx = _ctx()
        signal = None
        for i, c in enumerate(closes):
            bar = _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            strat.on_bar(bar, ctx)
            sig = strat.generate_signal(ctx)
            if sig is not None:
                signal = sig

        assert signal is not None
        assert signal.signal_type == SignalType.OPEN_LONG

    def test_no_signal_with_insufficient_bars(self):
        strat = DualMACrossoverStrategy()
        strat.on_init({"fast_period": 3, "slow_period": 5})

        ctx = _ctx()
        bar = _bar(start=datetime(2024, 1, 2, 9, 30))
        strat.on_bar(bar, ctx)

        signal = strat.generate_signal(ctx)
        assert signal is None

    def test_fast_period_must_be_less_than_slow(self):
        strat = DualMACrossoverStrategy()
        with pytest.raises(ValueError, match="fast_period"):
            strat.on_init({"fast_period": 20, "slow_period": 5})

    def test_fast_period_minimum(self):
        strat = DualMACrossoverStrategy()
        with pytest.raises(ValueError, match="fast_period"):
            strat.on_init({"fast_period": 1, "slow_period": 5})

    def test_slow_period_minimum(self):
        strat = DualMACrossoverStrategy()
        with pytest.raises(ValueError, match="slow_period"):
            strat.on_init({"fast_period": 3, "slow_period": 3})

    def test_death_cross_generates_close_long(self):
        strat = DualMACrossoverStrategy()
        strat.on_init({"fast_period": 3, "slow_period": 5})

        # Rising then falling to create death cross
        closes = ["10.00", "10.20", "10.40", "10.50", "10.30", "10.10", "9.90", "9.70", "9.50"]
        ctx = _ctx()
        signal = None
        for i, c in enumerate(closes):
            bar = _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            strat.on_bar(bar, ctx)
            sig = strat.generate_signal(ctx)
            if sig is not None:
                signal = sig

        assert signal is not None
        assert signal.signal_type == SignalType.CLOSE_LONG

    def test_no_signal_flat_ma(self):
        strat = DualMACrossoverStrategy()
        strat.on_init({"fast_period": 3, "slow_period": 5})

        # Flat prices -> no crossover
        closes = ["10.00"] * 10
        ctx = _ctx()
        for i, c in enumerate(closes):
            bar = _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            strat.on_bar(bar, ctx)

        signal = strat.generate_signal(ctx)
        assert signal is None


# ── CostModel Tests ──────────────────────────────────────────────────────────


class TestCostModel:
    def test_commission_above_min(self):
        cm = CostModel()
        # 1M amount * 0.0003 = 300 > 5
        assert cm.calculate_commission(Decimal("1000000")) == Decimal("300")

    def test_commission_below_min(self):
        cm = CostModel()
        # 1000 * 0.0003 = 0.3 < 5
        assert cm.calculate_commission(Decimal("1000")) == Decimal("5")

    def test_stamp_tax_sell_only(self):
        cm = CostModel()
        assert cm.calculate_stamp_tax(Decimal("100000"), Side.SELL) == Decimal("100")
        assert cm.calculate_stamp_tax(Decimal("100000"), Side.BUY) == Decimal("0")

    def test_total_cost(self):
        cm = CostModel(slippage=Decimal("0.01"))
        total = cm.calculate_total_cost(Decimal("100000"), Side.SELL, 1000)
        # commission=30, stamp_tax=100, slippage=10
        assert total == Decimal("140")


# ── PriceLimitRule Tests ────────────────────────────────────────────────────


class TestPriceLimitRule:
    def test_normal_stock_within_limit(self):
        rule = PriceLimitRule()
        assert rule.is_within_limit(Decimal("10.50"), Decimal("10.00"), False, "main") is True

    def test_normal_stock_exceeds_upper(self):
        rule = PriceLimitRule()
        assert rule.is_within_limit(Decimal("11.10"), Decimal("10.00"), False, "main") is False

    def test_st_stock_5pct_limit(self):
        rule = PriceLimitRule()
        # 10.50 / 10.00 = 1.05, exactly at 5% limit -> within
        assert rule.is_within_limit(Decimal("10.50"), Decimal("10.00"), True, "main") is True
        # 10.51 / 10.00 > 1.05 -> exceeds 5% limit
        assert rule.is_within_limit(Decimal("10.51"), Decimal("10.00"), True, "main") is False
        # 10.40 well within
        assert rule.is_within_limit(Decimal("10.40"), Decimal("10.00"), True, "main") is True

    def test_gem_stock_20pct_limit(self):
        rule = PriceLimitRule()
        assert rule.is_within_limit(Decimal("11.90"), Decimal("10.00"), False, "gem") is True

    def test_zero_prev_close(self):
        rule = PriceLimitRule()
        assert rule.is_within_limit(Decimal("10.00"), Decimal("0"), False, "main") is True


# ── BacktestMatcher Tests ────────────────────────────────────────────────────


class TestBacktestMatcher:
    def _make_matcher(self, **kwargs) -> BacktestMatcher:
        cost = CostModel(
            commission_rate=Decimal("0.0003"),
            commission_min=Decimal("5"),
            stamp_tax_rate=Decimal("0.001"),
            slippage=Decimal("0"),
        )
        price = PriceLimitRule()
        return BacktestMatcher(cost_model=cost, price_limit_rule=price, **kwargs)

    def _make_signal(self, signal_type: SignalType) -> Signal:
        now = datetime(2024, 1, 2, 9, 35)
        return Signal(
            signal_id="sig-1",
            strategy_instance_id="strat-1",
            strategy_version="v1",
            decision_time=now,
            instrument_id=InstrumentId("000001.SZ"),
            signal_type=signal_type,
            target_direction=TargetDirection.LONG,
            valid_until=now + timedelta(hours=1),
            cycle=Cycle.M5,
            created_at=now,
        )

    def test_buy_happy_path(self):
        matcher = self._make_matcher()
        signal = self._make_signal(SignalType.OPEN_LONG)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", close="10.20", volume=100000)

        result = matcher.match_order(
            signal=signal,
            target_bar=bar,
            prev_close=Decimal("10.00"),
            instrument=_instrument(),
            current_position=0,
            today_bought=0,
            available_cash=Decimal("1000000"),
        )
        assert result.filled is True
        assert result.fill_quantity > 0
        assert result.commission > 0

    def test_t_plus_1_blocks_sell_today(self):
        """Cannot sell shares bought today (T+1 rule)."""
        matcher = self._make_matcher()
        signal = self._make_signal(SignalType.CLOSE_LONG)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", volume=100000)

        result = matcher.match_order(
            signal=signal,
            target_bar=bar,
            prev_close=Decimal("10.00"),
            instrument=_instrument(),
            current_position=100,
            today_bought=100,  # All shares bought today
            available_cash=Decimal("0"),
        )
        assert result.filled is False
        assert result.reject_reason == "t_plus_1_blocked"

    def test_t_plus_1_allows_sell_yesterday(self):
        """Can sell shares bought before today."""
        matcher = self._make_matcher()
        signal = self._make_signal(SignalType.CLOSE_LONG)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", volume=100000)

        result = matcher.match_order(
            signal=signal,
            target_bar=bar,
            prev_close=Decimal("10.00"),
            instrument=_instrument(),
            current_position=200,
            today_bought=100,  # 100 bought today, 100 from yesterday
            available_cash=Decimal("0"),
        )
        assert result.filled is True
        assert result.fill_quantity == 100  # Can sell 100 (yesterday's)

    def test_lot_rounding(self):
        """Quantity rounded down to lot_size (100)."""
        matcher = self._make_matcher()
        signal = self._make_signal(SignalType.OPEN_LONG)
        # Price = 10, cash = 1500, max buy = 150 shares -> rounded to 100
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", volume=100000)

        result = matcher.match_order(
            signal=signal,
            target_bar=bar,
            prev_close=Decimal("10.00"),
            instrument=_instrument(),
            current_position=0,
            today_bought=0,
            available_cash=Decimal("1500"),
        )
        assert result.filled is True
        assert result.fill_quantity == 100

    def test_insufficient_cash_rejects(self):
        matcher = self._make_matcher()
        signal = self._make_signal(SignalType.OPEN_LONG)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", volume=100000)

        result = matcher.match_order(
            signal=signal,
            target_bar=bar,
            prev_close=Decimal("10.00"),
            instrument=_instrument(),
            current_position=0,
            today_bought=0,
            available_cash=Decimal("50"),  # Not enough for 1 lot
        )
        assert result.filled is False
        assert result.reject_reason == "insufficient_funds_or_volume"

    def test_zero_volume_bar_rejects(self):
        matcher = self._make_matcher()
        signal = self._make_signal(SignalType.OPEN_LONG)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", volume=0)

        result = matcher.match_order(
            signal=signal,
            target_bar=bar,
            prev_close=Decimal("10.00"),
            instrument=_instrument(),
            current_position=0,
            today_bought=0,
            available_cash=Decimal("1000000"),
        )
        assert result.filled is False

    def test_stamp_tax_on_sell_only(self):
        matcher = self._make_matcher()
        buy_signal = self._make_signal(SignalType.OPEN_LONG)
        sell_signal = self._make_signal(SignalType.CLOSE_LONG)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", volume=100000)

        buy_result = matcher.match_order(
            signal=buy_signal, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=0, today_bought=0,
            available_cash=Decimal("1000000"),
        )
        sell_result = matcher.match_order(
            signal=sell_signal, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=1000, today_bought=0,
            available_cash=Decimal("0"),
        )
        assert buy_result.stamp_tax == Decimal("0")
        assert sell_result.stamp_tax > 0

    def test_get_next_tradeable_bar(self):
        matcher = self._make_matcher()
        bars = [
            _bar(start=datetime(2024, 1, 2, 9, 35), cycle=Cycle.M1),
            _bar(start=datetime(2024, 1, 2, 9, 36), cycle=Cycle.M1),
            _bar(start=datetime(2024, 1, 2, 9, 37), cycle=Cycle.M1),
        ]
        next_bar = matcher.get_next_tradeable_bar(datetime(2024, 1, 2, 9, 35, 30), bars)
        assert next_bar is not None
        assert next_bar.bar_start_time == datetime(2024, 1, 2, 9, 36)

    def test_no_next_bar(self):
        matcher = self._make_matcher()
        bars = [_bar(start=datetime(2024, 1, 2, 9, 35), cycle=Cycle.M1)]
        next_bar = matcher.get_next_tradeable_bar(datetime(2024, 1, 2, 9, 36), bars)
        assert next_bar is None
