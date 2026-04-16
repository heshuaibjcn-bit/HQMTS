"""Tests for ReconciliationService — order/position/account comparison."""

from __future__ import annotations

import pytest

from hqmts.core.enums import ReconciliationStatus
from hqmts.reconciliation.service import ReconciliationService


@pytest.fixture
def service():
    return ReconciliationService()


class TestReconcileOrders:
    @pytest.mark.asyncio
    async def test_matching_orders(self, service):
        local = [{"order_id": "o1", "broker_order_id": "b1", "status": "filled", "filled_quantity": 100}]
        broker = [{"broker_order_id": "b1", "status": "filled", "filled_quantity": 100}]
        result = await service.reconcile_orders("acc-001", local, broker)
        assert result.status == ReconciliationStatus.MATCHED
        assert not result.has_mismatch

    @pytest.mark.asyncio
    async def test_status_mismatch(self, service):
        local = [{"order_id": "o1", "broker_order_id": "b1", "status": "pending", "filled_quantity": 0}]
        broker = [{"broker_order_id": "b1", "status": "filled", "filled_quantity": 100}]
        result = await service.reconcile_orders("acc-001", local, broker)
        assert result.status == ReconciliationStatus.MISMATCH_DETECTED
        assert any(d.field_name == "status" for d in result.diffs)

    @pytest.mark.asyncio
    async def test_filled_quantity_mismatch(self, service):
        local = [{"order_id": "o1", "broker_order_id": "b1", "status": "filled", "filled_quantity": 50}]
        broker = [{"broker_order_id": "b1", "status": "filled", "filled_quantity": 100}]
        result = await service.reconcile_orders("acc-001", local, broker)
        assert result.has_critical

    @pytest.mark.asyncio
    async def test_order_not_in_broker(self, service):
        local = [{"order_id": "o1", "broker_order_id": "b1", "status": "pending", "filled_quantity": 0}]
        broker = []
        result = await service.reconcile_orders("acc-001", local, broker)
        assert result.has_critical

    @pytest.mark.asyncio
    async def test_external_order_detected(self, service):
        local = []
        broker = [{"broker_order_id": "b-ext", "status": "filled", "filled_quantity": 200}]
        result = await service.reconcile_orders("acc-001", local, broker)
        assert result.external_events_detected == 1
        assert result.has_critical


class TestReconcilePositions:
    @pytest.mark.asyncio
    async def test_matching_positions(self, service):
        local = [{"instrument_id": "000001.SZ", "total_quantity": 500, "available_quantity": 500}]
        broker = [{"instrument_id": "000001.SZ", "total_quantity": 500, "available_quantity": 500}]
        result = await service.reconcile_positions("acc-001", local, broker)
        assert result.status == ReconciliationStatus.MATCHED

    @pytest.mark.asyncio
    async def test_quantity_mismatch(self, service):
        local = [{"instrument_id": "000001.SZ", "total_quantity": 500, "available_quantity": 500}]
        broker = [{"instrument_id": "000001.SZ", "total_quantity": 300, "available_quantity": 300}]
        result = await service.reconcile_positions("acc-001", local, broker)
        assert result.has_mismatch
        assert any(d.field_name == "total_quantity" for d in result.diffs)

    @pytest.mark.asyncio
    async def test_position_not_in_broker(self, service):
        local = [{"instrument_id": "000001.SZ", "total_quantity": 500, "available_quantity": 500}]
        broker = []
        result = await service.reconcile_positions("acc-001", local, broker)
        assert result.has_critical


class TestReconcileAccount:
    @pytest.mark.asyncio
    async def test_matching_account(self, service):
        local = {"total_asset": "1000000", "available_cash": "500000", "market_value": "500000"}
        broker = {"total_asset": "1000000", "available_cash": "500000", "market_value": "500000"}
        result = await service.reconcile_account("acc-001", local, broker)
        assert result.status == ReconciliationStatus.MATCHED

    @pytest.mark.asyncio
    async def test_cash_mismatch_is_critical(self, service):
        local = {"total_asset": "1000000", "available_cash": "500000", "market_value": "500000"}
        broker = {"total_asset": "1000000", "available_cash": "480000", "market_value": "520000"}
        result = await service.reconcile_account("acc-001", local, broker)
        assert result.has_critical
        cash_diff = [d for d in result.diffs if d.field_name == "available_cash"]
        assert len(cash_diff) == 1
        assert cash_diff[0].severity == "critical"


class TestReconcileTrades:
    @pytest.mark.asyncio
    async def test_matching_trades(self, service):
        local = [{"trade_id": "t1", "broker_trade_id": "bt1", "quantity": 100, "price": "10.50"}]
        broker = [{"broker_trade_id": "bt1", "quantity": 100, "price": "10.50"}]
        result = await service.reconcile_trades("acc-001", local, broker)
        assert result.status == ReconciliationStatus.MATCHED
        assert not result.has_mismatch

    @pytest.mark.asyncio
    async def test_quantity_mismatch(self, service):
        local = [{"trade_id": "t1", "broker_trade_id": "bt1", "quantity": 100, "price": "10.50"}]
        broker = [{"broker_trade_id": "bt1", "quantity": 50, "price": "10.50"}]
        result = await service.reconcile_trades("acc-001", local, broker)
        assert result.has_critical
        assert any(d.field_name == "quantity" for d in result.diffs)

    @pytest.mark.asyncio
    async def test_price_mismatch(self, service):
        local = [{"trade_id": "t1", "broker_trade_id": "bt1", "quantity": 100, "price": "10.50"}]
        broker = [{"broker_trade_id": "bt1", "quantity": 100, "price": "10.00"}]
        result = await service.reconcile_trades("acc-001", local, broker)
        assert result.has_critical
        assert any(d.field_name == "price" for d in result.diffs)

    @pytest.mark.asyncio
    async def test_external_trade_detected(self, service):
        local = []
        broker = [{"broker_trade_id": "bt-ext", "quantity": 200, "price": "15.00"}]
        result = await service.reconcile_trades("acc-001", local, broker)
        assert result.external_events_detected == 1
        assert result.has_critical

    @pytest.mark.asyncio
    async def test_trade_not_in_broker(self, service):
        local = [{"trade_id": "t1", "broker_trade_id": "bt1", "quantity": 100, "price": "10.50"}]
        broker = []
        result = await service.reconcile_trades("acc-001", local, broker)
        assert result.has_critical
