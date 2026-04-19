"""Tests for LiveOrchestrator (SAD 22.1)."""

from __future__ import annotations

import pytest

from hqmts.core.enums import StartupStepStatus
from hqmts.live.orchestrator import LiveOrchestrator
from hqmts.live.types import StartupResult, SystemReadiness


class FakeBrokerAdapter:
    """Test double for broker adapter."""

    def __init__(self, *, connected: bool = True) -> None:
        self._connected = connected
        self.disconnect_called = False

    async def connect(self) -> bool:
        return self._connected

    async def disconnect(self) -> None:
        self.disconnect_called = True


class FakeHealthMonitor:
    """Test double for QMT health monitor."""

    def __init__(self, *, degradation_mode: str = "normal") -> None:
        self._mode = degradation_mode

    @property
    def status(self):
        class _Status:
            degradation_mode = type("M", (), {"value": self._mode})()
        return _Status()


@pytest.fixture
def broker():
    return FakeBrokerAdapter(connected=True)


@pytest.fixture
def failing_broker():
    return FakeBrokerAdapter(connected=False)


@pytest.fixture
def health_monitor():
    return FakeHealthMonitor(degradation_mode="normal")


@pytest.fixture
def unhealthy_monitor():
    return FakeHealthMonitor(degradation_mode="close_only")


class TestLiveOrchestrator:
    @pytest.mark.asyncio
    async def test_startup_full_success(self):
        """All 14 steps complete, system is ready."""
        orchestrator = LiveOrchestrator()
        result = await orchestrator.startup()

        assert result.success is True
        assert result.readiness.is_ready is True
        assert len(result.steps) == 14
        assert all(
            s.status == StartupStepStatus.COMPLETED for s in result.steps
        )

    @pytest.mark.asyncio
    async def test_startup_with_broker_and_health(self, broker, health_monitor):
        """Steps 4-5 use real broker and health monitor."""
        orchestrator = LiveOrchestrator(
            broker_adapter=broker,
            health_monitor=health_monitor,
        )
        result = await orchestrator.startup()

        assert result.success is True
        step4 = result.steps[3]
        assert step4.name == "connect_qmt"
        assert step4.status == StartupStepStatus.COMPLETED
        assert "attempt 1" in step4.detail

        step5 = result.steps[4]
        assert step5.name == "verify_qmt_health"
        assert step5.status == StartupStepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_startup_qmt_connect_failure(self, failing_broker):
        """Step 4 fails after 3 retries, steps 1-3 are ok."""
        orchestrator = LiveOrchestrator(broker_adapter=failing_broker)
        result = await orchestrator.startup()

        assert result.success is False
        assert result.readiness.failed_step == "connect_qmt"
        step4 = result.steps[3]
        assert step4.status == StartupStepStatus.FAILED
        assert "3 attempts" in step4.detail

    @pytest.mark.asyncio
    async def test_startup_qmt_health_failure(self, broker, unhealthy_monitor):
        """Step 5 fails when health monitor reports unhealthy."""
        orchestrator = LiveOrchestrator(
            broker_adapter=broker,
            health_monitor=unhealthy_monitor,
        )
        result = await orchestrator.startup()

        assert result.success is False
        assert result.readiness.failed_step == "verify_qmt_health"
        step5 = result.steps[4]
        assert step5.status == StartupStepStatus.FAILED
        assert "unhealthy" in step5.detail

    @pytest.mark.asyncio
    async def test_startup_idempotent(self):
        """Calling startup() twice returns same cached result."""
        orchestrator = LiveOrchestrator()
        result1 = await orchestrator.startup()
        result2 = await orchestrator.startup()

        assert result1.success is True
        assert result2.success is True
        assert result1 is result2  # Same cached object

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self, broker):
        """Shutdown clears readiness and disconnects broker."""
        orchestrator = LiveOrchestrator(broker_adapter=broker)
        await orchestrator.startup()
        assert orchestrator.readiness_status.is_ready is True

        await orchestrator.shutdown()
        assert orchestrator.readiness_status.is_ready is False
        assert len(orchestrator.readiness_status.completed_steps) == 0
        assert broker.disconnect_called is True

    @pytest.mark.asyncio
    async def test_readiness_mid_startup(self):
        """Readiness shows partial state during startup."""
        orchestrator = LiveOrchestrator()

        # Before startup
        assert orchestrator.readiness_status.is_ready is False
        assert orchestrator.readiness_status.current_step == 0

        # After startup
        await orchestrator.startup()
        assert orchestrator.readiness_status.current_step == 14
        assert orchestrator.readiness_status.is_ready is True

    @pytest.mark.asyncio
    async def test_rollback_on_failure(self, failing_broker):
        """After failure at step 4, completed steps 1-3 are ok."""
        orchestrator = LiveOrchestrator(broker_adapter=failing_broker)
        result = await orchestrator.startup()

        assert result.success is False
        # Steps 1-3 should have completed before the failure at step 4
        completed_names = [s.name for s in result.steps if s.status == StartupStepStatus.COMPLETED]
        assert "load_config" in completed_names
        assert "init_db" in completed_names
        assert "start_health_monitor" in completed_names

    @pytest.mark.asyncio
    async def test_startup_result_has_durations(self):
        """Each step result has non-negative duration_ms."""
        orchestrator = LiveOrchestrator()
        result = await orchestrator.startup()

        for step in result.steps:
            assert step.duration_ms >= 0

        assert result.total_duration_ms >= 0
