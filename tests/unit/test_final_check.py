"""Tests for Final Pre-Submit Check."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from hqmts.core.enums import (
    FinalCheckResult,
    ReservationStatus,
    StrategyStatus,
)
from hqmts.risk.final_check import FinalCheckContext, FinalPreSubmitCheck


@pytest.fixture
def check():
    return FinalPreSubmitCheck()


@pytest.fixture
def passing_context():
    return FinalCheckContext(
        strategy_status=StrategyStatus.LIVE_RUNNING,
        signal_valid_until=datetime.now() + timedelta(minutes=5),
        qmt_adapter_available=True,
        account_risk_status="normal",
        available_quantity=1000,
        required_quantity=100,
        side="buy",
        reservation_status=ReservationStatus.ACTIVE,
        reservation_expires_at=datetime.now() + timedelta(minutes=2),
        has_conflicting_inflight=False,
        kill_switch_active=False,
        close_only_mode=False,
        pause_open_mode=False,
        orders_last_minute=3,
        max_orders_per_minute=10,
        price=Decimal("10.50"),
        quantity=100,
        instrument_id="000001.SZ",
        source_is_deterministic=True,
        request_from_execution_service=True,
    )


class TestFinalPreSubmitCheck:
    @pytest.mark.asyncio
    async def test_all_pass(self, check, passing_context):
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.ALLOW
        assert len(result.failed_checks) == 0

    @pytest.mark.asyncio
    async def test_kill_switch_rejects(self, check, passing_context):
        passing_context.kill_switch_active = True
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.REJECT
        assert "kill_switch_active" in result.failed_checks

    @pytest.mark.asyncio
    async def test_kill_switch_allows_flatten(self, check, passing_context):
        passing_context.kill_switch_active = True
        passing_context.is_flatten = True
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.ALLOW

    @pytest.mark.asyncio
    async def test_expired_signal_rejected(self, check, passing_context):
        passing_context.signal_valid_until = datetime.now() - timedelta(minutes=1)
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.REJECT
        assert "signal_expired" in result.failed_checks

    @pytest.mark.asyncio
    async def test_qmt_unavailable_retry(self, check, passing_context):
        passing_context.qmt_adapter_available = False
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.RETRY_LATER
        assert "qmt_unavailable" in result.failed_checks

    @pytest.mark.asyncio
    async def test_non_deterministic_source_rejected(self, check, passing_context):
        passing_context.source_is_deterministic = False
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.REJECT
        assert "source_non_deterministic" in result.failed_checks

    @pytest.mark.asyncio
    async def test_unauthorized_source_rejected(self, check, passing_context):
        passing_context.request_from_execution_service = False
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.REJECT
        assert "unauthorized_source" in result.failed_checks

    @pytest.mark.asyncio
    async def test_expired_reservation_rejected(self, check, passing_context):
        passing_context.reservation_expires_at = datetime.now() - timedelta(minutes=1)
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.REJECT
        assert "reservation_expired" in result.failed_checks

    @pytest.mark.asyncio
    async def test_close_only_rejects_buy(self, check, passing_context):
        passing_context.close_only_mode = True
        passing_context.side = "buy"
        result = await check.execute(passing_context)
        assert "close_only_no_buy" in result.failed_checks

    @pytest.mark.asyncio
    async def test_close_only_allows_sell(self, check, passing_context):
        passing_context.close_only_mode = True
        passing_context.side = "sell"
        result = await check.execute(passing_context)
        assert result.result == FinalCheckResult.ALLOW

    @pytest.mark.asyncio
    async def test_frequency_exceeded(self, check, passing_context):
        passing_context.orders_last_minute = 10
        result = await check.execute(passing_context)
        assert "frequency_exceeded" in result.failed_checks

    @pytest.mark.asyncio
    async def test_invalid_params(self, check, passing_context):
        passing_context.price = Decimal("0")
        result = await check.execute(passing_context)
        assert "params_invalid" in result.failed_checks

    @pytest.mark.asyncio
    async def test_conflicting_inflight(self, check, passing_context):
        passing_context.has_conflicting_inflight = True
        result = await check.execute(passing_context)
        assert "conflicting_inflight" in result.failed_checks

    @pytest.mark.asyncio
    async def test_insufficient_position_for_sell(self, check, passing_context):
        passing_context.side = "sell"
        passing_context.available_quantity = 50
        passing_context.required_quantity = 100
        result = await check.execute(passing_context)
        assert "position_insufficient" in result.failed_checks

    @pytest.mark.asyncio
    async def test_t1_blocks_today_bought_shares(self, check, passing_context):
        """T+1: shares bought today cannot be sold today."""
        passing_context.side = "sell"
        passing_context.available_quantity = 500
        passing_context.today_bought_quantity = 500
        passing_context.quantity = 100
        result = await check.execute(passing_context)
        assert "position_insufficient_t1_all_blocked" in result.failed_checks

    @pytest.mark.asyncio
    async def test_t1_partial_block(self, check, passing_context):
        """T+1: only some shares blocked, sellable remainder is enough."""
        passing_context.side = "sell"
        passing_context.available_quantity = 500
        passing_context.today_bought_quantity = 300
        passing_context.quantity = 200
        result = await check.execute(passing_context)
        assert "position_sufficient" in result.passed_checks

    @pytest.mark.asyncio
    async def test_t1_partial_block_insufficient(self, check, passing_context):
        """T+1: sellable remainder is not enough for the order."""
        passing_context.side = "sell"
        passing_context.available_quantity = 500
        passing_context.today_bought_quantity = 300
        passing_context.quantity = 250
        result = await check.execute(passing_context)
        assert "position_insufficient" in result.failed_checks
