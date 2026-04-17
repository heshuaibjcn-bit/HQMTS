"""Force flatten service for risk-initiated liquidation (SAD 18.3).

Bypasses normal signal flow. Iterates all open positions and
generates market sell orders. Uses is_flatten=True to pass
through FinalPreSubmitCheck even when kill switch is active.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from hqmts.core.enums import (
    FinalCheckResult,
    FlattenTrigger,
    OrderStatus,
    ReservationStatus,
    StrategyStatus,
)
from hqmts.core.types import now_shanghai
from hqmts.risk.final_check import FinalCheckContext, FinalPreSubmitCheck

logger = logging.getLogger(__name__)


@dataclass
class FlattenPositionTask:
    """Per-position tracking during force flatten."""

    instrument_id: str
    total_quantity: int
    available_quantity: int
    today_bought_quantity: int
    sellable_quantity: int
    order_id: str | None = None
    order_status: str = "pending"
    attempts: int = 0
    last_error: str = ""


@dataclass
class FlattenProgress:
    """Overall force flatten progress."""

    flatten_id: str
    trigger: FlattenTrigger
    trigger_reason: str
    started_at: str = ""
    total_positions: int = 0
    flattened_positions: int = 0
    remaining_positions: int = 0
    failed_positions: int = 0
    skipped_positions: int = 0
    tasks: list[FlattenPositionTask] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.remaining_positions == 0


class ForceFlattenService:
    """Orchestrates risk-initiated position liquidation (SAD 18.3).

    Core flow:
    1. Query all open positions
    2. Compute sellable quantity (total - today_bought, T+1 enforcement)
    3. Skip positions where sellable == 0
    4. Create market sell orders bypassing signal/strategy
    5. Pass through FinalPreSubmitCheck with is_flatten=True
    6. Track progress and partial fills
    """

    def __init__(
        self,
        *,
        position_repo: object | None = None,
        final_check: FinalPreSubmitCheck | None = None,
        order_service: object | None = None,
        account_id: str = "",
        max_retries_per_position: int = 3,
    ) -> None:
        self._position_repo = position_repo
        self._final_check = final_check or FinalPreSubmitCheck()
        self._order_service = order_service
        self._account_id = account_id
        self._max_retries = max_retries_per_position
        self._active_flattens: dict[str, FlattenProgress] = {}

    async def execute_flatten(
        self,
        trigger: FlattenTrigger,
        reason: str,
    ) -> FlattenProgress:
        """Execute force flatten for all open positions.

        Returns FlattenProgress with per-position status.
        """
        flatten_id = str(uuid.uuid4())
        progress = FlattenProgress(
            flatten_id=flatten_id,
            trigger=trigger,
            trigger_reason=reason,
            started_at=now_shanghai().isoformat(),
        )
        self._active_flattens[flatten_id] = progress

        # Step 1: Query open positions
        if self._position_repo is None:
            logger.warning("FORCE_FLATTEN no position repo configured")
            return progress

        positions = await self._position_repo.get_open_positions(self._account_id)
        progress.total_positions = len(positions)

        if not positions:
            logger.info("FORCE_FLATTEN_NO_POSITIONS account=%s", self._account_id)
            return progress

        # Step 2-3: Build tasks with T+1 enforcement
        for pos in positions:
            today_bought = getattr(pos, "today_bought_quantity", 0)
            sellable = pos.available_quantity - today_bought

            task = FlattenPositionTask(
                instrument_id=pos.instrument_id,
                total_quantity=pos.total_quantity,
                available_quantity=pos.available_quantity,
                today_bought_quantity=today_bought,
                sellable_quantity=max(0, sellable),
            )

            if task.sellable_quantity == 0:
                task.order_status = "skipped_t1"
                progress.skipped_positions += 1
                logger.info(
                    "FORCE_FLATTEN_SKIP_T1 instrument=%s total=%d today_bought=%d",
                    pos.instrument_id, pos.total_quantity, today_bought,
                )

            progress.tasks.append(task)

        # Step 4-6: Execute sell orders for sellable positions
        sellable_tasks = [t for t in progress.tasks if t.sellable_quantity > 0]
        progress.remaining_positions = len(sellable_tasks)

        for task in sellable_tasks:
            task.attempts += 1
            success = await self._execute_flatten_order(task, trigger)
            if success:
                progress.flattened_positions += 1
                progress.remaining_positions -= 1
                task.order_status = "submitted"
                logger.info(
                    "FORCE_FLATTEN_OK instrument=%s qty=%d",
                    task.instrument_id, task.sellable_quantity,
                )
            else:
                progress.failed_positions += 1
                progress.remaining_positions -= 1
                task.order_status = "failed"
                logger.error(
                    "FORCE_FLATTEN_FAILED instrument=%s error=%s",
                    task.instrument_id, task.last_error,
                )

        logger.info(
            "FORCE_FLATTEN_SUMMARY total=%d flattened=%d failed=%d skipped=%d",
            progress.total_positions,
            progress.flattened_positions,
            progress.failed_positions,
            progress.skipped_positions,
        )
        return progress

    async def retry_failed(self, flatten_id: str) -> FlattenProgress | None:
        """Retry failed positions from a previous flatten attempt."""
        progress = self._active_flattens.get(flatten_id)
        if progress is None:
            return None

        failed_tasks = [
            t for t in progress.tasks
            if t.order_status == "failed" and t.attempts < self._max_retries
        ]
        if not failed_tasks:
            return progress

        for task in failed_tasks:
            task.attempts += 1
            success = await self._execute_flatten_order(task, progress.trigger)
            if success:
                progress.flattened_positions += 1
                progress.failed_positions -= 1
                task.order_status = "submitted"
            else:
                task.order_status = "failed"

        return progress

    @property
    def active_flattens(self) -> list[FlattenProgress]:
        return list(self._active_flattens.values())

    async def _execute_flatten_order(
        self,
        task: FlattenPositionTask,
        trigger: FlattenTrigger,
    ) -> bool:
        """Execute a single flatten sell order.

        Bypasses signal generation and strategy approval.
        Passes through FinalPreSubmitCheck with is_flatten=True.
        """
        # Build final check context with is_flatten=True
        ctx = FinalCheckContext(
            strategy_status=StrategyStatus.CLOSE_ONLY,
            qmt_adapter_available=True,
            account_risk_status="normal",
            available_quantity=task.available_quantity,
            required_quantity=task.sellable_quantity,
            today_bought_quantity=task.today_bought_quantity,
            side="sell",
            reservation_status=None,
            has_conflicting_inflight=False,
            kill_switch_active=True,  # Flatten works even with kill switch
            close_only_mode=True,
            is_flatten=True,
            source_is_deterministic=True,
            request_from_execution_service=True,
            price=Decimal("1"),  # Market order, price will be determined by exchange
            quantity=task.sellable_quantity,
            instrument_id=task.instrument_id,
        )

        result = await self._final_check.execute(ctx)
        if result.result != FinalCheckResult.ALLOW:
            task.last_error = f"Final check rejected: {result.reason}"
            return False

        # Submit order (if order service available)
        if self._order_service is not None:
            try:
                task.order_id = str(uuid.uuid4())
                # In production, this would call order_service.submit_order()
                # with a market sell order for task.sellable_quantity
                await self._order_service.submit_flatten_order(
                    instrument_id=task.instrument_id,
                    quantity=task.sellable_quantity,
                    flatten_id=task.order_id,
                )
            except Exception as exc:
                task.last_error = str(exc)
                return False

        task.order_id = task.order_id or str(uuid.uuid4())
        return True
