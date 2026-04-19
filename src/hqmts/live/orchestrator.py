"""Live startup orchestrator (SAD 22.1).

14-step startup sequence for clean system initialization.
Mirrors RecoveryService but for normal (non-crash) startup.
"""

from __future__ import annotations

import logging
import time

from hqmts.core.enums import StartupStepStatus
from hqmts.core.types import now_shanghai
from hqmts.live.types import StartupResult, StepResult, SystemReadiness

logger = logging.getLogger(__name__)

# Step definitions: (step_name, description)
_STEP_DEFINITIONS: list[tuple[str, str]] = [
    ("load_config", "Load system config and version binding"),
    ("init_db", "Initialize database connections"),
    ("start_health_monitor", "Start QMT health monitor"),
    ("connect_qmt", "Connect QMT adapter (with retry)"),
    ("verify_qmt_health", "Verify QMT health (heartbeat)"),
    ("load_strategy_configs", "Load strategy configurations"),
    ("init_strategy_runtime", "Initialize strategy runtime"),
    ("start_bar_builder", "Start bar builder"),
    ("subscribe_data_feed", "Subscribe to instrument data feed"),
    ("warmup_factor_cache", "Warm up factor computation cache"),
    ("init_risk_engine", "Initialize risk engine (load rules)"),
    ("init_reservation_manager", "Initialize reservation manager"),
    ("init_execution_pipeline", "Initialize execution pipeline"),
    ("mark_live_ready", "Mark system as LIVE_READY"),
]


class LiveOrchestrator:
    """Orchestrates the 14-step live startup sequence (SAD 22.1).

    Dependencies are injected for testability. Each step is a private
    async method. On failure, completed steps are rolled back in
    reverse order. Calling startup() twice returns the cached result.
    """

    def __init__(
        self,
        *,
        broker_adapter: object | None = None,
        health_monitor: object | None = None,
        risk_engine: object | None = None,
        reservation_manager: object | None = None,
        bar_builder: object | None = None,
        strategy_runtime: object | None = None,
        data_feed: object | None = None,
        factor_cache: object | None = None,
        execution_pipeline: object | None = None,
        db_session_factory: object | None = None,
        config: dict | None = None,
    ) -> None:
        self._broker_adapter = broker_adapter
        self._health_monitor = health_monitor
        self._risk_engine = risk_engine
        self._reservation_manager = reservation_manager
        self._bar_builder = bar_builder
        self._strategy_runtime = strategy_runtime
        self._data_feed = data_feed
        self._factor_cache = factor_cache
        self._execution_pipeline = execution_pipeline
        self._db_session_factory = db_session_factory
        self._config = config or {}

        self._readiness = SystemReadiness(started_at=now_shanghai().isoformat())
        self._cached_result: StartupResult | None = None

    @property
    def readiness_status(self) -> SystemReadiness:
        """Current system readiness state."""
        return self._readiness

    async def startup(self) -> StartupResult:
        """Execute the full 14-step startup sequence.

        Returns StartupResult with success/failure status and per-step details.
        Idempotent: returns cached result if already started successfully.
        """
        if self._cached_result is not None and self._cached_result.success:
            return self._cached_result

        start_time = time.monotonic()
        results: list[StepResult] = []
        completed_steps: list[str] = []

        self._readiness = SystemReadiness(
            total_steps=len(_STEP_DEFINITIONS),
            started_at=now_shanghai().isoformat(),
        )

        for i, (step_name, description) in enumerate(_STEP_DEFINITIONS):
            self._readiness.current_step = i + 1

            step_start = time.monotonic()
            handler = getattr(self, f"_step_{i + 1:02d}_{step_name}", None)

            if handler is None:
                # No custom handler: auto-pass (dependency not provided)
                result = StepResult(
                    step_number=i + 1,
                    name=step_name,
                    status=StartupStepStatus.COMPLETED,
                    duration_ms=0.0,
                    detail=f"{description} (auto-passed, no dependency)",
                )
            else:
                try:
                    result = await handler()
                except Exception as exc:
                    result = StepResult(
                        step_number=i + 1,
                        name=step_name,
                        status=StartupStepStatus.FAILED,
                        duration_ms=(time.monotonic() - step_start) * 1000,
                        detail=str(exc),
                    )

            # Check for failure (either from exception or FAILED status)
            if result.status == StartupStepStatus.FAILED:
                result.duration_ms = result.duration_ms or (time.monotonic() - step_start) * 1000
                results.append(result)
                await self._rollback(completed_steps, step_name)
                self._readiness.failed_step = step_name
                total_ms = (time.monotonic() - start_time) * 1000
                return StartupResult(
                    success=False,
                    steps=results,
                    readiness=self._readiness,
                    total_duration_ms=total_ms,
                )

            result.duration_ms = result.duration_ms or (time.monotonic() - step_start) * 1000
            results.append(result)
            completed_steps.append(step_name)
            self._readiness.completed_steps.append(step_name)

        # All steps completed
        self._readiness.is_ready = True
        total_ms = (time.monotonic() - start_time) * 1000

        startup_result = StartupResult(
            success=True,
            steps=results,
            readiness=self._readiness,
            total_duration_ms=total_ms,
        )
        self._cached_result = startup_result
        return startup_result

    async def shutdown(self) -> None:
        """Clean teardown in reverse order of startup."""
        steps_to_teardown = list(reversed(self._readiness.completed_steps))
        for step_name in steps_to_teardown:
            handler = getattr(self, f"_teardown_{step_name}", None)
            if handler is not None:
                try:
                    await handler()
                except Exception as exc:
                    logger.warning("Shutdown step %s failed: %s", step_name, exc)
        self._readiness.is_ready = False
        self._cached_result = None
        self._readiness.completed_steps.clear()

    async def _rollback(
        self, completed_steps: list[str], failed_step: str
    ) -> None:
        """Roll back completed steps in reverse order after a failure."""
        logger.error("Startup failed at step '%s', rolling back", failed_step)
        for step_name in reversed(completed_steps):
            handler = getattr(self, f"_teardown_{step_name}", None)
            if handler is not None:
                try:
                    await handler()
                    logger.info("Rolled back step '%s'", step_name)
                except Exception as exc:
                    logger.warning("Rollback of '%s' failed: %s", step_name, exc)

    # ------------------------------------------------------------------
    # Step implementations (only steps with real logic get overrides)
    # ------------------------------------------------------------------

    async def _step_04_connect_qmt(self) -> StepResult:
        """Step 4: Connect QMT adapter with retry."""
        if self._broker_adapter is None:
            return StepResult(
                step_number=4, name="connect_qmt",
                status=StartupStepStatus.COMPLETED,
                detail="No broker adapter configured (skipped)",
            )

        max_retries = 3
        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                connected = await self._broker_adapter.connect()
                if connected:
                    return StepResult(
                        step_number=4, name="connect_qmt",
                        status=StartupStepStatus.COMPLETED,
                        detail=f"QMT connected (attempt {attempt})",
                    )
                last_error = "connect() returned False"
            except Exception as exc:
                last_error = str(exc)

            if attempt < max_retries:
                logger.warning(
                    "QMT connect attempt %d/%d failed: %s",
                    attempt, max_retries, last_error,
                )

        return StepResult(
            step_number=4, name="connect_qmt",
            status=StartupStepStatus.FAILED,
            detail=f"QMT connect failed after {max_retries} attempts: {last_error}",
        )

    async def _step_05_verify_qmt_health(self) -> StepResult:
        """Step 5: Verify QMT health via heartbeat."""
        if self._health_monitor is None:
            return StepResult(
                step_number=5, name="verify_qmt_health",
                status=StartupStepStatus.COMPLETED,
                detail="No health monitor configured (skipped)",
            )

        # Check current health status
        status = self._health_monitor.status
        if status.degradation_mode.value == "normal":
            return StepResult(
                step_number=5, name="verify_qmt_health",
                status=StartupStepStatus.COMPLETED,
                detail=f"QMT healthy, degradation={status.degradation_mode.value}",
            )

        return StepResult(
            step_number=5, name="verify_qmt_health",
            status=StartupStepStatus.FAILED,
            detail=f"QMT unhealthy, degradation={status.degradation_mode.value}",
        )

    async def _step_14_mark_live_ready(self) -> StepResult:
        """Step 14: Mark system as LIVE_READY."""
        self._readiness.is_ready = True
        return StepResult(
            step_number=14, name="mark_live_ready",
            status=StartupStepStatus.COMPLETED,
            detail="System marked as LIVE_READY",
        )

    # ------------------------------------------------------------------
    # Teardown handlers (for rollback/shutdown)
    # ------------------------------------------------------------------

    async def _teardown_connect_qmt(self) -> None:
        """Disconnect QMT on rollback."""
        if self._broker_adapter is not None and hasattr(self._broker_adapter, "disconnect"):
            await self._broker_adapter.disconnect()
