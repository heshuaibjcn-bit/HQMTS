"""Tests for BacktestOrder, richer strategy interface, SL/TP triggers, and matcher extensions."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.cost import CostModel, PriceLimitRule
from hqmts.backtest.engine import BacktestConfig, BacktestEngine
from hqmts.backtest.matcher import BacktestMatcher
from hqmts.backtest.order import BacktestOrder
from hqmts.backtest.portfolio import PortfolioState, Position
from hqmts.backtest.strategy import DualMACrossoverStrategy, StrategyTemplate
from hqmts.core.enums import Cycle, Side, SignalType
from hqmts.core.types import InstrumentId, SignalId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument
from hqmts.domain.signal import Signal


# ── Helpers ──────────────────────────────────────────────────────────────────


def _bar(
    start: datetime,
    instrument_id: str = "000001.SZ",
    close: str = "10.00",
    open_: str = "10.00",
    high: str = "10.50",
    low: str = "9.50",
    volume: int = 100000,
    cycle: Cycle = Cycle.M5,
) -> Bar:
    return Bar(
        instrument_id=InstrumentId(instrument_id),
        cycle=cycle,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes={Cycle.M1: 1, Cycle.M5: 5, Cycle.M15: 15, Cycle.M30: 30, Cycle.M60: 60}[cycle]),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        amount=Decimal("1000000"),
        is_completed=True,
        source="test",
        data_version=VersionStr("v1"),
    )


def _instrument(instrument_id: str = "000001.SZ") -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(instrument_id),
        ts_code=instrument_id,
        exchange="SZSE",
        symbol=instrument_id.split(".")[0],
        name="TestStock",
    )


# ── BacktestOrder Tests ──────────────────────────────────────────────────────


class TestBacktestOrder:
    def test_defaults(self):
        order = BacktestOrder(instrument_id="000001.SZ", side=Side.BUY)
        assert order.quantity == 0
        assert order.order_type == "market"
        assert order.limit_price is None
        assert order.stop_loss is None
        assert order.take_profit is None
        assert order.signal_id == ""
        assert order.reason_code == ""

    def test_limit_order(self):
        order = BacktestOrder(
            instrument_id="000001.SZ",
            side=Side.BUY,
            quantity=100,
            order_type="limit",
            limit_price=Decimal("10.00"),
        )
        assert order.order_type == "limit"
        assert order.limit_price == Decimal("10.00")

    def test_with_sl_tp(self):
        order = BacktestOrder(
            instrument_id="000001.SZ",
            side=Side.BUY,
            quantity=100,
            stop_loss=Decimal("9.00"),
            take_profit=Decimal("12.00"),
        )
        assert order.stop_loss == Decimal("9.00")
        assert order.take_profit == Decimal("12.00")


# ── Position SL/TP Tests ─────────────────────────────────────────────────────


class TestPositionSLTP:
    def test_stop_loss_triggered(self):
        pos = Position(instrument_id="000001.SZ", quantity=100, stop_loss=Decimal("9.50"))
        assert pos.check_stop_loss(Decimal("9.40")) is True

    def test_stop_loss_not_triggered(self):
        pos = Position(instrument_id="000001.SZ", quantity=100, stop_loss=Decimal("9.50"))
        assert pos.check_stop_loss(Decimal("9.60")) is False

    def test_stop_loss_none(self):
        pos = Position(instrument_id="000001.SZ", quantity=100)
        assert pos.check_stop_loss(Decimal("5.00")) is False

    def test_stop_loss_zero_quantity(self):
        pos = Position(instrument_id="000001.SZ", quantity=0, stop_loss=Decimal("9.50"))
        assert pos.check_stop_loss(Decimal("9.00")) is False

    def test_take_profit_triggered(self):
        pos = Position(instrument_id="000001.SZ", quantity=100, take_profit=Decimal("12.00"))
        assert pos.check_take_profit(Decimal("12.50")) is True

    def test_take_profit_not_triggered(self):
        pos = Position(instrument_id="000001.SZ", quantity=100, take_profit=Decimal("12.00"))
        assert pos.check_take_profit(Decimal("11.50")) is False

    def test_take_profit_none(self):
        pos = Position(instrument_id="000001.SZ", quantity=100)
        assert pos.check_take_profit(Decimal("20.00")) is False


# ── PortfolioState SL/TP Tests ───────────────────────────────────────────────


class TestPortfolioSLTP:
    def test_update_stop_loss_take_profit(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        state.positions["000001.SZ"] = Position(instrument_id="000001.SZ", quantity=100)
        state.update_stop_loss_take_profit("000001.SZ", Decimal("9.00"), Decimal("12.00"))
        assert state.positions["000001.SZ"].stop_loss == Decimal("9.00")
        assert state.positions["000001.SZ"].take_profit == Decimal("12.00")

    def test_check_stop_loss_triggers(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        state.positions["000001.SZ"] = Position(
            instrument_id="000001.SZ", quantity=100, stop_loss=Decimal("9.50")
        )
        triggered = state.check_stop_loss_triggers({"000001.SZ": Decimal("9.00")})
        assert "000001.SZ" in triggered

    def test_check_stop_loss_no_trigger(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        state.positions["000001.SZ"] = Position(
            instrument_id="000001.SZ", quantity=100, stop_loss=Decimal("9.50")
        )
        triggered = state.check_stop_loss_triggers({"000001.SZ": Decimal("10.00")})
        assert "000001.SZ" not in triggered

    def test_check_take_profit_triggers(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        state.positions["000001.SZ"] = Position(
            instrument_id="000001.SZ", quantity=100, take_profit=Decimal("11.00")
        )
        triggered = state.check_take_profit_triggers({"000001.SZ": Decimal("11.50")})
        assert "000001.SZ" in triggered


# ── Strategy generate_orders() Tests ─────────────────────────────────────────


class TestGenerateOrders:
    def test_default_delegation_no_signal(self):
        """When generate_signal returns None, generate_orders returns empty list."""
        strat = DualMACrossoverStrategy()
        strat.on_init({"fast_period": 3, "slow_period": 5})
        ctx = StrategyContext(
            strategy_instance_id=StrategyInstanceId("test"),
            strategy_version=VersionStr("v1"),
            instrument_id=InstrumentId("000001.SZ"),
            cycle=Cycle.M5,
            decision_time=datetime(2024, 1, 2, 9, 35),
        )
        orders = strat.generate_orders(ctx)
        assert orders == []

    def test_default_delegation_wraps_signal(self):
        """When generate_signal returns a Signal, generate_orders wraps it in BacktestOrder."""
        strat = DualMACrossoverStrategy()
        strat.on_init({"fast_period": 3, "slow_period": 5})
        # Feed enough bars to trigger a golden cross
        closes = ["10.00", "9.80", "9.60", "9.50", "9.40", "9.30", "9.40", "9.50", "9.60", "9.70",
                  "9.80", "10.00", "10.20", "10.30", "10.40", "10.50", "10.60", "10.70", "10.80", "10.90"]
        for i, c in enumerate(closes):
            bar = _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            ctx = StrategyContext(
                strategy_instance_id=StrategyInstanceId("test"),
                strategy_version=VersionStr("v1"),
                instrument_id=InstrumentId("000001.SZ"),
                cycle=Cycle.M5,
                decision_time=bar.bar_start_time,
            )
            strat.on_bar(bar, ctx)
            orders = strat.generate_orders(ctx)

        # Should have produced at least one order — check with a fresh strategy instance
        # Find the non-empty result
        strat2 = DualMACrossoverStrategy()
        strat2.on_init({"fast_period": 3, "slow_period": 5})
        last_orders = []
        for i, c in enumerate(closes):
            bar = _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            ctx = StrategyContext(
                strategy_instance_id=StrategyInstanceId("test"),
                strategy_version=VersionStr("v1"),
                instrument_id=InstrumentId("000001.SZ"),
                cycle=Cycle.M5,
                decision_time=bar.bar_start_time,
            )
            strat2.on_bar(bar, ctx)
            result = strat2.generate_orders(ctx)
            if result:
                last_orders = result

        assert len(last_orders) == 1
        assert last_orders[0].side == Side.BUY
        assert last_orders[0].instrument_id == "000001.SZ"

    def test_custom_strategy_with_sl_tp(self):
        """Strategy that overrides generate_orders with SL/TP."""
        class SLTPStrategy(StrategyTemplate):
            def __init__(self):
                self._should_buy = False

            def on_init(self, params):
                pass

            def on_bar(self, bar, context):
                if bar.close > Decimal("10.00"):
                    self._should_buy = True

            def generate_signal(self, context):
                return None

            def generate_orders(self, context):
                if self._should_buy:
                    self._should_buy = False
                    return [BacktestOrder(
                        instrument_id=str(context.instrument_id),
                        side=Side.BUY,
                        quantity=100,
                        stop_loss=Decimal("9.00"),
                        take_profit=Decimal("12.00"),
                        signal_id="custom-001",
                    )]
                return []

        strat = SLTPStrategy()
        strat.on_init({})
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), close="10.50")
        ctx = StrategyContext(
            strategy_instance_id=StrategyInstanceId("test"),
            strategy_version=VersionStr("v1"),
            instrument_id=InstrumentId("000001.SZ"),
            cycle=Cycle.M5,
            decision_time=bar.bar_start_time,
        )
        strat.on_bar(bar, ctx)
        orders = strat.generate_orders(ctx)
        assert len(orders) == 1
        assert orders[0].stop_loss == Decimal("9.00")
        assert orders[0].take_profit == Decimal("12.00")


# ── Matcher match_order_from_bt Tests ────────────────────────────────────────


class TestMatcherFromBT:
    def _make_matcher(self) -> BacktestMatcher:
        cost_model = CostModel(
            commission_rate=Decimal("0.0003"),
            commission_min=Decimal("5"),
            stamp_tax_rate=Decimal("0.001"),
        )
        return BacktestMatcher(
            cost_model=cost_model,
            price_limit_rule=PriceLimitRule(),
            lot_size=100,
            participation_rate=0.25,
        )

    def test_market_buy(self):
        matcher = self._make_matcher()
        order = BacktestOrder(instrument_id="000001.SZ", side=Side.BUY, quantity=100)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", close="10.00")
        result = matcher.match_order_from_bt(
            order=order, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=0, today_bought=0,
            available_cash=Decimal("100000"),
        )
        assert result.filled
        assert result.fill_quantity == 100
        assert result.fill_price == Decimal("10.00")

    def test_sell_quantity_zero_means_all_available(self):
        matcher = self._make_matcher()
        order = BacktestOrder(instrument_id="000001.SZ", side=Side.SELL, quantity=0)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", close="10.00")
        result = matcher.match_order_from_bt(
            order=order, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=500, today_bought=0,
            available_cash=Decimal("0"),
        )
        assert result.filled
        # Should sell up to volume cap (25% of 100000 = 25000, limited by position 500)
        assert result.fill_quantity == 500

    def test_limit_buy_not_reached(self):
        matcher = self._make_matcher()
        order = BacktestOrder(
            instrument_id="000001.SZ", side=Side.BUY, quantity=100,
            order_type="limit", limit_price=Decimal("9.50"),
        )
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", close="10.00")
        result = matcher.match_order_from_bt(
            order=order, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=0, today_bought=0,
            available_cash=Decimal("100000"),
        )
        assert not result.filled
        assert result.reject_reason == "limit_price_not_reached"

    def test_limit_buy_filled_when_price_at_limit(self):
        matcher = self._make_matcher()
        order = BacktestOrder(
            instrument_id="000001.SZ", side=Side.BUY, quantity=100,
            order_type="limit", limit_price=Decimal("10.00"),
        )
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", close="10.00")
        result = matcher.match_order_from_bt(
            order=order, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=0, today_bought=0,
            available_cash=Decimal("100000"),
        )
        assert result.filled

    def test_limit_sell_not_reached(self):
        matcher = self._make_matcher()
        order = BacktestOrder(
            instrument_id="000001.SZ", side=Side.SELL, quantity=100,
            order_type="limit", limit_price=Decimal("11.00"),
        )
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", close="10.00")
        result = matcher.match_order_from_bt(
            order=order, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=500, today_bought=0,
            available_cash=Decimal("0"),
        )
        assert not result.filled
        assert result.reject_reason == "limit_price_not_reached"

    def test_t_plus_1_blocked(self):
        matcher = self._make_matcher()
        order = BacktestOrder(instrument_id="000001.SZ", side=Side.SELL, quantity=100)
        bar = _bar(start=datetime(2024, 1, 2, 9, 35), open_="10.00", close="10.00")
        result = matcher.match_order_from_bt(
            order=order, target_bar=bar, prev_close=Decimal("10.00"),
            instrument=_instrument(), current_position=100, today_bought=100,
            available_cash=Decimal("0"),
        )
        assert not result.filled
        assert result.reject_reason == "t_plus_1_blocked"


# ── Engine SL/TP Integration Tests ──────────────────────────────────────────


class TestEngineSLTP:
    def test_stop_loss_triggers_sell(self):
        """After buying, declining price triggers stop-loss sell."""
        # Custom strategy that buys on first bar then nothing
        class BuyOnceStrategy(StrategyTemplate):
            def __init__(self):
                self._bought = False

            def on_init(self, params):
                pass

            def on_bar(self, bar, context):
                pass

            def generate_signal(self, context):
                return None

            def generate_orders(self, context):
                if not self._bought:
                    self._bought = True
                    return [BacktestOrder(
                        instrument_id=str(context.instrument_id),
                        side=Side.BUY,
                        quantity=100,
                        stop_loss=Decimal("9.50"),
                        signal_id="buy-1",
                    )]
                return []

        config = BacktestConfig(
            strategy=BuyOnceStrategy(),
            strategy_name="buy_once",
            strategy_version="v1",
            strategy_params={},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
        )
        engine = BacktestEngine(config)

        # Day 1: buy at 10.00
        # Day 2: price drops to 9.00, stop-loss should trigger
        day1_bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00")
            for i in range(5)
        ]
        day2_bars = [
            _bar(start=datetime(2024, 1, 3, 9, 30) + timedelta(minutes=5 * i),
                 close="9.00", open_="9.00")
            for i in range(5)
        ]
        result = engine.run({"000001.SZ": day1_bars + day2_bars})

        # Should have a buy and a stop-loss sell
        buys = [t for t in engine._portfolio.trades if t.side == "buy"]
        sells = [t for t in engine._portfolio.trades if t.side == "sell"]
        assert len(buys) >= 1
        assert len(sells) >= 1  # Stop-loss triggered

    def test_take_profit_triggers_sell(self):
        """After buying, rising price triggers take-profit sell."""
        class BuyOnceTPStrategy(StrategyTemplate):
            def __init__(self):
                self._bought = False

            def on_init(self, params):
                pass

            def on_bar(self, bar, context):
                pass

            def generate_signal(self, context):
                return None

            def generate_orders(self, context):
                if not self._bought:
                    self._bought = True
                    return [BacktestOrder(
                        instrument_id=str(context.instrument_id),
                        side=Side.BUY,
                        quantity=100,
                        take_profit=Decimal("11.00"),
                        signal_id="buy-tp-1",
                    )]
                return []

        config = BacktestConfig(
            strategy=BuyOnceTPStrategy(),
            strategy_name="buy_once_tp",
            strategy_version="v1",
            strategy_params={},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
        )
        engine = BacktestEngine(config)

        day1_bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00")
            for i in range(5)
        ]
        day2_bars = [
            _bar(start=datetime(2024, 1, 3, 9, 30) + timedelta(minutes=5 * i),
                 close="11.50", open_="11.50")
            for i in range(5)
        ]
        result = engine.run({"000001.SZ": day1_bars + day2_bars})

        sells = [t for t in engine._portfolio.trades if t.side == "sell"]
        assert len(sells) >= 1  # Take-profit triggered
