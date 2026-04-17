"""Tests for MockQMT adapter (FR-LIVE-001 scaffold)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hqmts.execution.qmt_mock import MockQMTAdapter


class TestMockQMTLifecycle:
    def test_connect(self):
        adapter = MockQMTAdapter()
        assert adapter.connect() is True
        assert adapter.is_connected() is True

    def test_disconnect(self):
        adapter = MockQMTAdapter()
        adapter.connect()
        assert adapter.disconnect() is True
        assert adapter.is_connected() is False

    def test_not_connected_raises(self):
        adapter = MockQMTAdapter()
        with pytest.raises(RuntimeError, match="not connected"):
            adapter.query_account()


class TestMockQMTAccount:
    def test_default_account(self):
        adapter = MockQMTAdapter()
        adapter.connect()
        account = adapter.query_account()
        assert account.available_cash == Decimal("1000000")
        assert account.account_id == "mock-account-001"

    def test_custom_initial_cash(self):
        adapter = MockQMTAdapter(initial_cash=Decimal("500000"))
        adapter.connect()
        account = adapter.query_account()
        assert account.available_cash == Decimal("500000")


class TestMockQMOrders:
    @pytest.fixture
    def adapter(self):
        a = MockQMTAdapter()
        a.connect()
        return a

    def test_submit_order_returns_id(self, adapter):
        order_id = adapter.submit_order(
            instrument_id="000001.SZ",
            side="buy",
            order_type="limit",
            price=Decimal("10.50"),
            quantity=100,
        )
        assert order_id.startswith("mock-")

    def test_submit_order_filled(self, adapter):
        adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 100)
        orders = adapter.query_orders()
        assert len(orders) == 1
        assert orders[0].status == "filled"
        assert orders[0].filled_quantity == 100

    def test_cancel_order(self, adapter):
        order_id = adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 100)
        result = adapter.cancel_order(order_id)
        # Already filled, so cancel returns False
        assert result is False

    def test_cancel_nonexistent_order(self, adapter):
        result = adapter.cancel_order("nonexistent")
        assert result is False

    def test_fill_status(self, adapter):
        order_id = adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 100)
        fill = adapter.get_fill_status(order_id)
        assert fill.filled_quantity == 100
        assert fill.status == "filled"

    def test_fill_status_unknown_order(self, adapter):
        with pytest.raises(ValueError, match="Unknown order"):
            adapter.get_fill_status("nonexistent")

    def test_query_orders_empty(self, adapter):
        assert adapter.query_orders() == []


class TestMockQMTPartialFill:
    def test_partial_fill(self):
        adapter = MockQMTAdapter(partial_fill=True)
        adapter.connect()
        order_id = adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 100)
        fill = adapter.get_fill_status(order_id)
        assert fill.filled_quantity == 50
        assert fill.status == "partial"


class TestMockQMTFailureInjection:
    def test_fail_submit(self):
        adapter = MockQMTAdapter(fail_submit=True)
        adapter.connect()
        with pytest.raises(RuntimeError, match="forced submit failure"):
            adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 100)


class TestMockQMTPositions:
    def test_buy_creates_position(self):
        adapter = MockQMTAdapter()
        adapter.connect()
        adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 100)
        positions = adapter.query_positions()
        assert len(positions) == 1
        assert positions[0].instrument_id == "000001.SZ"
        assert positions[0].quantity == 100
        assert positions[0].available_quantity == 0  # T+1

    def test_sell_reduces_position(self):
        adapter = MockQMTAdapter()
        adapter.connect()
        adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 200)
        adapter.submit_order("000001.SZ", "sell", "limit", Decimal("11.00"), 100)
        positions = adapter.query_positions()
        assert len(positions) == 1
        assert positions[0].quantity == 100

    def test_sell_all_removes_position(self):
        adapter = MockQMTAdapter()
        adapter.connect()
        adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.50"), 100)
        adapter.submit_order("000001.SZ", "sell", "limit", Decimal("11.00"), 100)
        assert adapter.query_positions() == []

    def test_weighted_average_cost(self):
        adapter = MockQMTAdapter()
        adapter.connect()
        adapter.submit_order("000001.SZ", "buy", "limit", Decimal("10.00"), 100)
        adapter.submit_order("000001.SZ", "buy", "limit", Decimal("12.00"), 100)
        positions = adapter.query_positions()
        assert positions[0].cost_price == Decimal("11.00")  # (10*100 + 12*100) / 200
