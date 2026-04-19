"""Tests for ForceFlattenService (SAD 18.3)."""

from __future__ import annotations

import pytest
from dataclasses import dataclass
from decimal import Decimal

from hqmts.core.enums import FinalCheckResult, FlattenTrigger
from hqmts.risk.final_check import FinalCheckContext, FinalPreSubmitCheck
from hqmts.risk.force_flatten import (
    FlattenProgress,
    FlattenPositionTask,
    ForceFlattenService,
)


@dataclass
class FakePosition:
    """Test double for position ORM."""

    instrument_id: str
    total_quantity: int
    available_quantity: int
    today_bought_quantity: int = 0


class FakePositionRepo:
    """Test double for position repository."""

    def __init__(self, positions: list[FakePosition] | None = None) -> None:
        self._positions = positions or []

    async def get_open_positions(self, account_id: str) -> list[FakePosition]:
        return list(self._positions)


class FakeOrderService:
    """Test double for order service."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.submitted: list[dict] = []
        self._should_fail = should_fail

    async def submit_flatten_order(
        self, instrument_id: str, quantity: int, flatten_id: str
    ) -> None:
        if self._should_fail:
            raise RuntimeError("Order submission failed")
        self.submitted.append({
            "instrument_id": instrument_id,
            "quantity": quantity,
            "flatten_id": flatten_id,
        })


@pytest.fixture
def final_check():
    return FinalPreSubmitCheck()


@pytest.fixture
def three_positions():
    return [
        FakePosition("000001.SZ", 1000, 1000, 0),
        FakePosition("600000.SH", 500, 500, 0),
        FakePosition("000002.SZ", 300, 300, 0),
    ]


@pytest.fixture
def service(final_check):
    return ForceFlattenService(
        final_check=final_check,
        account_id="test_account",
    )


class TestForceFlattenService:
    @pytest.mark.asyncio
    async def test_flatten_three_positions(self, final_check, three_positions):
        """All 3 positions flattened successfully."""
        svc = ForceFlattenService(
            position_repo=FakePositionRepo(three_positions),
            final_check=final_check,
            order_service=FakeOrderService(),
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.KILL_SWITCH, "Kill switch activated",
        )

        assert progress.total_positions == 3
        assert progress.flattened_positions == 3
        assert progress.failed_positions == 0
        assert progress.is_complete is True

    @pytest.mark.asyncio
    async def test_flatten_with_t1_restriction(self, final_check):
        """Position fully bought today is skipped."""
        positions = [
            FakePosition("000001.SZ", 1000, 1000, 1000),  # All bought today
        ]
        svc = ForceFlattenService(
            position_repo=FakePositionRepo(positions),
            final_check=final_check,
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.KILL_SWITCH, "Kill switch",
        )

        assert progress.total_positions == 1
        assert progress.skipped_positions == 1
        assert progress.flattened_positions == 0
        assert progress.tasks[0].order_status == "skipped_t1"

    @pytest.mark.asyncio
    async def test_flatten_partial_t1(self, final_check):
        """Only the non-T1 portion is sold."""
        positions = [
            FakePosition("000001.SZ", 500, 500, 300),  # 200 sellable
        ]
        svc = ForceFlattenService(
            position_repo=FakePositionRepo(positions),
            final_check=final_check,
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.KILL_SWITCH, "Kill switch",
        )

        assert progress.total_positions == 1
        assert progress.flattened_positions == 1
        assert progress.tasks[0].sellable_quantity == 200

    @pytest.mark.asyncio
    async def test_flatten_with_order_failure(self, final_check):
        """One position fails to submit."""
        positions = [
            FakePosition("000001.SZ", 1000, 1000, 0),
        ]
        svc = ForceFlattenService(
            position_repo=FakePositionRepo(positions),
            final_check=final_check,
            order_service=FakeOrderService(should_fail=True),
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.KILL_SWITCH, "Kill switch",
        )

        assert progress.failed_positions == 1
        assert progress.flattened_positions == 0
        assert "failed" in progress.tasks[0].order_status

    @pytest.mark.asyncio
    async def test_flatten_kill_switch_allows_flatten(self, final_check):
        """Kill switch active but is_flatten=True passes final check."""
        # This is tested implicitly through the execute_flatten flow
        # which sets is_flatten=True and kill_switch_active=True in context
        positions = [FakePosition("000001.SZ", 100, 100, 0)]
        svc = ForceFlattenService(
            position_repo=FakePositionRepo(positions),
            final_check=final_check,
            order_service=FakeOrderService(),
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.KILL_SWITCH, "Kill switch",
        )

        # The flatten order should succeed even with kill switch
        assert progress.flattened_positions == 1

    @pytest.mark.asyncio
    async def test_flatten_progress_tracking(self, final_check):
        """Progress shows correct counts at each stage."""
        positions = [
            FakePosition("000001.SZ", 1000, 1000, 0),  # Sellable
            FakePosition("600000.SH", 500, 500, 500),   # All T+1 blocked
            FakePosition("000002.SZ", 300, 300, 0),     # Sellable
        ]
        svc = ForceFlattenService(
            position_repo=FakePositionRepo(positions),
            final_check=final_check,
            order_service=FakeOrderService(),
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.MAX_DRAWDOWN, "Max drawdown exceeded",
        )

        assert progress.total_positions == 3
        assert progress.flattened_positions == 2
        assert progress.skipped_positions == 1
        assert progress.trigger == FlattenTrigger.MAX_DRAWDOWN

    @pytest.mark.asyncio
    async def test_flatten_empty_positions(self, final_check):
        """No positions to flatten returns immediately."""
        svc = ForceFlattenService(
            position_repo=FakePositionRepo([]),
            final_check=final_check,
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.MANUAL_COMMAND, "Manual flatten",
        )

        assert progress.total_positions == 0
        assert progress.is_complete is True

    @pytest.mark.asyncio
    async def test_retry_failed(self, final_check):
        """Failed positions can be retried."""
        positions = [FakePosition("000001.SZ", 100, 100, 0)]
        order_svc = FakeOrderService(should_fail=True)
        svc = ForceFlattenService(
            position_repo=FakePositionRepo(positions),
            final_check=final_check,
            order_service=order_svc,
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.KILL_SWITCH, "Kill switch",
        )
        assert progress.failed_positions == 1

        # Fix the order service and retry
        order_svc._should_fail = False
        retried = await svc.retry_failed(progress.flatten_id)
        assert retried is not None
        assert retried.flattened_positions == 1
        assert retried.failed_positions == 0

    @pytest.mark.asyncio
    async def test_retry_unknown_flatten_id(self, service):
        """Retry with unknown ID returns None."""
        result = await service.retry_failed("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_active_flattens_tracked(self, final_check):
        """Active flattens are accessible via property."""
        svc = ForceFlattenService(
            position_repo=FakePositionRepo([]),
            final_check=final_check,
            account_id="test",
        )
        await svc.execute_flatten(FlattenTrigger.RISK_RULE, "Risk rule")
        assert len(svc.active_flattens) == 1
