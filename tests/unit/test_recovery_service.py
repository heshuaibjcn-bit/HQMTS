"""Tests for RecoveryService — startup recovery, step execution, and default mode."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hqmts.core.enums import StrategyStatus
from hqmts.db.base import Base
from hqmts.recovery.service import (
    BrokerAdapter,
    FakeBrokerAdapter,
    RecoveryContext,
    RecoveryService,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """In-memory SQLite session for recovery tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def context() -> RecoveryContext:
    return RecoveryContext(
        account_id="acc-001",
        strategy_instance_id="strat-inst-001",
        trigger_reason="system_restart",
    )


@pytest.fixture
def broker() -> FakeBrokerAdapter:
    return FakeBrokerAdapter(
        connected=True,
        positions=[{"instrument_id": "000001.SZ", "total_quantity": 100, "available_quantity": 100}],
        orders=[],
        trades=[],
    )


@pytest.fixture
def service(db_session: AsyncSession, broker: FakeBrokerAdapter) -> RecoveryService:
    return RecoveryService(session=db_session, broker_adapter=broker)


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------


class TestRecoverySession:
    @pytest.mark.asyncio
    async def test_create_recovery_session(self, service: RecoveryService):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="system_restart",
        )
        session = await service.create_recovery_session(ctx)
        assert session["trigger_reason"] == "system_restart"
        assert len(session["steps"]) == 14

    @pytest.mark.asyncio
    async def test_error_orders_flagged(self, service: RecoveryService):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="crash",
            has_error_orders=True,
        )
        session = await service.create_recovery_session(ctx)
        reconcile_step = session["steps"][6]  # step 7 (0-indexed)
        assert "note" in reconcile_step

    @pytest.mark.asyncio
    async def test_external_events_flagged(self, service: RecoveryService):
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
    async def test_expired_reservations_flagged(self, service: RecoveryService):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
            has_expired_reservations=True,
        )
        session = await service.create_recovery_session(ctx)
        restore_step = session["steps"][5]  # step 6
        assert "note" in restore_step


# ---------------------------------------------------------------------------
# Initial mode determination
# ---------------------------------------------------------------------------


class TestDetermineInitialMode:
    def test_default_is_pause_open(self, service: RecoveryService):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
        )
        mode = service.determine_initial_mode(ctx)
        assert mode == StrategyStatus.PAUSE_OPEN

    def test_external_events_to_close_only(self, service: RecoveryService):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
            has_external_events=True,
        )
        mode = service.determine_initial_mode(ctx)
        assert mode == StrategyStatus.CLOSE_ONLY

    def test_position_mismatch_to_close_only(self, service: RecoveryService):
        ctx = RecoveryContext(
            account_id="acc-001",
            strategy_instance_id="strat-001",
            trigger_reason="restart",
            has_position_mismatch=True,
        )
        mode = service.determine_initial_mode(ctx)
        assert mode == StrategyStatus.CLOSE_ONLY


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


class TestExecuteRecoveryStep:
    @pytest.mark.asyncio
    async def test_execute_step_verify_clock(self, service: RecoveryService):
        step = await service.execute_recovery_step("session-001", "verify_clock")
        assert step.name == "verify_clock"
        assert step.status == "completed"
        assert "Clock verified" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_load_config(self, service: RecoveryService):
        step = await service.execute_recovery_step("session-001", "load_config")
        assert step.status == "completed"
        assert "Config loaded" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_connect_qmt(self, service: RecoveryService):
        step = await service.execute_recovery_step("session-001", "connect_qmt")
        assert step.status == "completed"
        assert "connected" in step.result.lower()

    @pytest.mark.asyncio
    async def test_execute_step_connect_qmt_failure(self, db_session: AsyncSession):
        bad_broker = FakeBrokerAdapter(connected=False)
        svc = RecoveryService(session=db_session, broker_adapter=bad_broker)
        step = await svc.execute_recovery_step("s-1", "connect_qmt")
        assert step.status == "failed"
        assert "Failed" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_query_broker_state(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "query_broker_state", context,
        )
        assert step.status == "completed"
        assert "positions=1" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_load_local_state(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "load_local_state", context,
        )
        assert step.status == "completed"
        assert "Found 0 active orders" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_restore_reservations(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "restore_reservations", context,
        )
        assert step.status == "completed"
        assert "Released 0 expired" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_reconcile_orders(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "reconcile_orders", context,
        )
        assert step.status == "completed"
        assert "diffs=" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_reconcile_trades(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "reconcile_trades", context,
        )
        assert step.status == "completed"
        assert "diffs=" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_reconcile_positions(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "reconcile_positions", context,
        )
        # No local positions, broker has 1 → critical diffs expected
        assert "diffs=" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_check_external_events(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "check_external_events", context,
        )
        assert step.status == "completed"
        assert "Found 0 unhandled" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_rebuild_context(self, service: RecoveryService):
        step = await service.execute_recovery_step("session-001", "rebuild_context")
        assert step.status == "completed"

    @pytest.mark.asyncio
    async def test_execute_step_establish_session(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "establish_session", context,
        )
        assert step.status == "completed"
        assert "persisted" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_default_pause_open(
        self, service: RecoveryService, context: RecoveryContext,
    ):
        step = await service.execute_recovery_step(
            "session-001", "default_pause_open", context,
        )
        assert step.status == "completed"
        assert "pause_open" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_wait_approval(self, service: RecoveryService):
        step = await service.execute_recovery_step("session-001", "wait_approval")
        assert step.status == "pending"
        assert "Waiting" in step.result

    @pytest.mark.asyncio
    async def test_execute_unknown_step(self, service: RecoveryService):
        step = await service.execute_recovery_step("session-001", "nonexistent_step")
        assert step.status == "failed"
        assert "No handler" in step.result

    @pytest.mark.asyncio
    async def test_execute_step_without_context(
        self, service: RecoveryService,
    ):
        """Steps requiring context should fail gracefully when context is None."""
        step = await service.execute_recovery_step("s-1", "query_broker_state")
        assert step.status == "failed"
        assert "No recovery context" in step.result


# ---------------------------------------------------------------------------
# FakeBrokerAdapter
# ---------------------------------------------------------------------------


class TestFakeBrokerAdapter:
    @pytest.mark.asyncio
    async def test_connect_returns_configured(self):
        broker = FakeBrokerAdapter(connected=True)
        assert await broker.connect() is True

        broker_off = FakeBrokerAdapter(connected=False)
        assert await broker_off.connect() is False

    @pytest.mark.asyncio
    async def test_query_returns_canned_data(self):
        broker = FakeBrokerAdapter(
            positions=[{"instrument_id": "000001.SZ"}],
            orders=[{"broker_order_id": "bo-1"}],
            trades=[{"broker_trade_id": "bt-1"}],
            account={"available_cash": "12345"},
        )
        assert len(await broker.query_positions("a1")) == 1
        assert len(await broker.query_orders("a1")) == 1
        assert len(await broker.query_trades("a1")) == 1
        assert (await broker.query_account("a1"))["available_cash"] == "12345"
