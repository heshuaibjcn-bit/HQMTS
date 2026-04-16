"""Tests for RecoveryService — startup recovery and default mode."""

from __future__ import annotations

import pytest

from hqmts.core.enums import StrategyStatus
from hqmts.recovery.service import RecoveryContext, RecoveryService


@pytest.fixture
def service():
    return RecoveryService()


class TestRecoverySession:
    @pytest.mark.asyncio
    async def test_create_recovery_session(self, service):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="system_restart",
        )
        session = await service.create_recovery_session(ctx)
        assert session["trigger_reason"] == "system_restart"
        assert len(session["steps"]) == 14

    @pytest.mark.asyncio
    async def test_uncertain_orders_flagged(self, service):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="crash",
            has_uncertain_orders=True,
        )
        session = await service.create_recovery_session(ctx)
        reconcile_step = session["steps"][6]  # step 7 (0-indexed)
        assert "note" in reconcile_step

    @pytest.mark.asyncio
    async def test_external_events_flagged(self, service):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
            has_external_events=True,
        )
        session = await service.create_recovery_session(ctx)
        check_step = session["steps"][9]  # step 10
        assert "note" in check_step

    @pytest.mark.asyncio
    async def test_expired_reservations_flagged(self, service):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
            has_expired_reservations=True,
        )
        session = await service.create_recovery_session(ctx)
        restore_step = session["steps"][5]  # step 6
        assert "note" in restore_step


class TestDetermineInitialMode:
    def test_default_is_pause_open(self, service):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
        )
        mode = service.determine_initial_mode(ctx)
        assert mode == StrategyStatus.PAUSE_OPEN

    def test_external_events_to_close_only(self, service):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
            has_external_events=True,
        )
        mode = service.determine_initial_mode(ctx)
        assert mode == StrategyStatus.CLOSE_ONLY

    def test_position_mismatch_to_close_only(self, service):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
            has_position_mismatch=True,
        )
        mode = service.determine_initial_mode(ctx)
        assert mode == StrategyStatus.CLOSE_ONLY


class TestExecuteRecoveryStep:
    @pytest.mark.asyncio
    async def test_execute_step(self, service):
        step = await service.execute_recovery_step("session-001", "verify_clock")
        assert step.name == "verify_clock"
        assert step.status == "completed"
