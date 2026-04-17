"""Tests for paper trading mode (FR-BT-005)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from hqmts.core.enums import Cycle, SignalType
from hqmts.core.types import InstrumentId, StrategyInstanceId
from hqmts.domain.signal import Signal
from hqmts.execution.paper_trading import (
    PaperOrder,
    PaperOrderStatus,
    PaperPosition,
    PaperTradingEngine,
    PaperTradingState,
)


def _make_signal(
    instrument_id: str = "000001.SZ",
    signal_type: SignalType = SignalType.OPEN_LONG,
) -> Signal:
    base = datetime(2024, 1, 2, 9, 35)
    return Signal(
        signal_id="sig-001",
        strategy_instance_id=StrategyInstanceId("strat-1"),
        strategy_version="v1.0",
        decision_time=base,
        instrument_id=InstrumentId(instrument_id),
        cycle=Cycle.M5,
        signal_type=signal_type,
        valid_until=base.replace(hour=15),
        created_at=base,
    )


# Use generous initial_cash so buy orders don't exceed it after commission
CASH = Decimal("2000000")


class TestPaperOrder:
    def test_default_status(self):
        order = PaperOrder(
            order_id="o1", signal_id="s1", instrument_id="000001.SZ",
            side="buy", order_type="market", price=Decimal("10"), quantity=100,
        )
        assert order.status == PaperOrderStatus.PENDING
        assert order.fill_price == Decimal("0")
        assert order.fill_quantity == 0

    def test_rejected_order(self):
        order = PaperOrder(
            order_id="o1", signal_id="s1", instrument_id="000001.SZ",
            side="buy", order_type="market", price=Decimal("10"), quantity=0,
            status=PaperOrderStatus.REJECTED,
            reject_reason="Insufficient cash",
        )
        assert order.status == PaperOrderStatus.REJECTED
        assert order.reject_reason == "Insufficient cash"


class TestPaperTradingEngine:
    def test_initial_state(self):
        engine = PaperTradingEngine(
            session_id="sess-1",
            strategy_name="test_strategy",
            initial_cash=Decimal("500000"),
        )
        assert engine.state.session_id == "sess-1"
        assert engine.state.strategy_name == "test_strategy"
        assert engine.state.cash == Decimal("500000")
        assert engine.state.initial_cash == Decimal("500000")
        assert engine.state.is_active

    def test_submit_buy_signal(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, reference_price=Decimal("10.00"))

        assert order.side == "buy"
        assert order.instrument_id == "000001.SZ"
        assert order.quantity > 0
        assert order.status == PaperOrderStatus.PENDING
        assert order.price == Decimal("10.00")

    def test_submit_buy_insufficient_cash(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=Decimal("50"))
        signal = _make_signal()
        order = engine.submit_signal(signal, reference_price=Decimal("10.00"))

        assert order.status == PaperOrderStatus.REJECTED
        assert order.quantity == 0

    def test_submit_sell_signal_no_position(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test")
        signal = _make_signal(signal_type=SignalType.CLOSE_LONG)
        order = engine.submit_signal(signal, reference_price=Decimal("10.00"))

        assert order.status == PaperOrderStatus.REJECTED
        assert order.quantity == 0

    def test_submit_sell_with_position(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        buy_signal = _make_signal()
        buy_order = engine.submit_signal(buy_signal, Decimal("10.00"))
        engine.fill_order(buy_order, Decimal("10.00"))
        engine.end_of_day_reset()

        sell_signal = _make_signal(signal_type=SignalType.CLOSE_LONG)
        sell_order = engine.submit_signal(sell_signal, Decimal("10.50"))
        assert sell_order.side == "sell"
        assert sell_order.status == PaperOrderStatus.PENDING
        assert sell_order.quantity > 0

    def test_fill_buy_order(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("10.00"))
        filled = engine.fill_order(order, Decimal("10.00"))

        assert filled.status == PaperOrderStatus.FILLED
        assert filled.fill_price == Decimal("10.00")
        assert filled.fill_quantity == filled.quantity
        assert filled.commission > Decimal("0")
        assert filled.filled_at is not None

    def test_fill_buy_updates_cash(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("10.00"))
        cash_before = engine.state.cash
        engine.fill_order(order, Decimal("10.00"))

        assert engine.state.cash < cash_before

    def test_fill_buy_creates_position(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("10.00"))
        engine.fill_order(order, Decimal("10.00"))

        pos = engine.state.positions.get("000001.SZ")
        assert pos is not None
        assert pos.quantity > 0
        assert pos.available_quantity == 0  # T+1
        assert pos.today_bought == pos.quantity

    def test_fill_sell_order(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        buy_signal = _make_signal()
        buy_order = engine.submit_signal(buy_signal, Decimal("10.00"))
        engine.fill_order(buy_order, Decimal("10.00"))
        engine.end_of_day_reset()

        sell_signal = _make_signal(signal_type=SignalType.CLOSE_LONG)
        sell_order = engine.submit_signal(sell_signal, Decimal("11.00"))
        filled = engine.fill_order(sell_order, Decimal("11.00"))

        assert filled.status == PaperOrderStatus.FILLED
        assert filled.stamp_tax > Decimal("0")  # Stamp tax on sell

    def test_fill_sell_increases_cash(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        buy_signal = _make_signal()
        buy_order = engine.submit_signal(buy_signal, Decimal("10.00"))
        engine.fill_order(buy_order, Decimal("10.00"))
        engine.end_of_day_reset()

        cash_before = engine.state.cash
        sell_signal = _make_signal(signal_type=SignalType.CLOSE_LONG)
        sell_order = engine.submit_signal(sell_signal, Decimal("11.00"))
        engine.fill_order(sell_order, Decimal("11.00"))

        assert engine.state.cash > cash_before

    def test_fill_sell_removes_position_when_empty(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        buy_signal = _make_signal()
        buy_order = engine.submit_signal(buy_signal, Decimal("10.00"))
        engine.fill_order(buy_order, Decimal("10.00"))
        engine.end_of_day_reset()

        sell_signal = _make_signal(signal_type=SignalType.CLOSE_LONG)
        sell_order = engine.submit_signal(sell_signal, Decimal("11.00"))
        engine.fill_order(sell_order, Decimal("11.00"))

        assert "000001.SZ" not in engine.state.positions

    def test_fill_rejected_if_not_pending(self):
        order = PaperOrder(
            order_id="o1", signal_id="s1", instrument_id="000001.SZ",
            side="buy", order_type="market", price=Decimal("10"), quantity=100,
            status=PaperOrderStatus.FILLED,
        )
        engine = PaperTradingEngine(session_id="s1", strategy_name="test")
        result = engine.fill_order(order, Decimal("10.00"))
        assert result.status == PaperOrderStatus.FILLED  # No change

    def test_fill_rejected_insufficient_cash(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=Decimal("100"))
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("1.00"))
        # Drain cash after order submission
        engine.state.cash = Decimal("0")
        filled = engine.fill_order(order, Decimal("1.00"))

        assert filled.status == PaperOrderStatus.REJECTED
        assert "Insufficient cash" in filled.reject_reason

    def test_commission_minimum(self):
        engine = PaperTradingEngine(
            session_id="s1", strategy_name="test",
            initial_cash=CASH,
            commission_rate=Decimal("0.0003"),
            commission_min=Decimal("5"),
        )
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("1.00"))
        filled = engine.fill_order(order, Decimal("1.00"))

        # At least one lot (100 shares) at price 1 => commission = 100 * 1 * 0.0003 = 0.03 < 5
        assert filled.commission >= Decimal("5")

    def test_end_of_day_reset(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("10.00"))
        engine.fill_order(order, Decimal("10.00"))

        # Before EOD: available = 0 (T+1)
        pos = engine.state.positions["000001.SZ"]
        assert pos.available_quantity == 0

        engine.end_of_day_reset()

        # After EOD: available = quantity
        assert pos.available_quantity == pos.quantity
        assert pos.today_bought == 0

    def test_end_of_day_snapshot(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("10.00"))
        engine.fill_order(order, Decimal("10.00"))
        engine.end_of_day_reset()

        assert len(engine.state.daily_snapshots) == 1
        snap = engine.state.daily_snapshots[0]
        assert "date" in snap
        assert "cash" in snap
        assert "total_asset" in snap
        assert "positions" in snap

    def test_get_total_asset_with_prices(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("10.00"))
        engine.fill_order(order, Decimal("10.00"))

        total = engine.get_total_asset(prices={"000001.SZ": Decimal("11.00")})
        assert total > engine.state.cash

    def test_get_total_asset_without_prices(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        signal = _make_signal()
        order = engine.submit_signal(signal, Decimal("10.00"))
        engine.fill_order(order, Decimal("10.00"))

        total = engine.get_total_asset()
        assert total == engine.state.cash + Decimal("10.00") * Decimal(order.quantity)

    def test_stop_session(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test")
        assert engine.state.is_active
        engine.stop()
        assert not engine.state.is_active

    def test_cost_price_averaging_on_second_buy(self):
        engine = PaperTradingEngine(session_id="s1", strategy_name="test", initial_cash=CASH)
        # First buy
        signal1 = _make_signal()
        order1 = engine.submit_signal(signal1, Decimal("10.00"))
        engine.fill_order(order1, Decimal("10.00"))
        engine.end_of_day_reset()

        # Second buy at different price
        signal2 = _make_signal()
        order2 = engine.submit_signal(signal2, Decimal("12.00"))
        engine.fill_order(order2, Decimal("12.00"))

        pos = engine.state.positions["000001.SZ"]
        total_qty = order1.quantity + order2.quantity
        expected_cost = (Decimal("10.00") * Decimal(order1.quantity) + Decimal("12.00") * Decimal(order2.quantity)) / Decimal(total_qty)
        assert pos.cost_price == expected_cost

    def test_paper_position_defaults(self):
        pos = PaperPosition(instrument_id="000001.SZ")
        assert pos.quantity == 0
        assert pos.available_quantity == 0
        assert pos.cost_price == Decimal("0")
