"""Recovery service (SAD Sections 15.5, 22).

Handles system startup recovery, restart sequence, and fault recovery.
Default: enter pause_open, wait for human confirmation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from hqmts.core.enums import RecoveryStatus, StrategyStatus
from hqmts.core.types import RecoveryId


@dataclass
class RecoveryContext:
    """Context for a recovery session."""

    account_id: str
    strategy_instance_id: str
    trigger_reason: str
    has_uncertain_orders: bool = False
    has_position_mismatch: bool = False
    has_external_events: bool = False
    has_expired_reservations: bool = False


@dataclass
class RecoveryStep:
    """A single step in the recovery process."""

    step_number: int
    name: str
    description: str
    status: str = "pending"  # pending, completed, failed, skipped
    result: str = ""


class RecoveryService:
    """Orchestrates system recovery per SAD 22.1.

    14-step startup sequence:
    1. Load config and approval state
    2. Verify clock sync
    3. Connect QMT
    4. Query account/positions/today's orders/trades
    5. Load local unfinished states
    6. Restore CashReservations
    7. Order reconciliation
    8. Trade reconciliation
    9. Position reconciliation
    10. Check external manual events
    11. Rebuild DecisionSnapshot/Strategy context
    12. Establish RecoverySession
    13. Default to pause_open
    14. Wait for human or rule approval to resume

    Agent can generate recovery suggestions but cannot bypass pending_confirmation.
    """

    async def create_recovery_session(
        self,
        context: RecoveryContext,
    ) -> dict:
        """Create a new recovery session."""
        session_id = str(uuid.uuid4())
        now = datetime.now()

        return {
            "recovery_session_id": session_id,
            "scope_type": "strategy",
            "scope_id": context.strategy_instance_id,
            "trigger_reason": context.trigger_reason,
            "status": RecoveryStatus.CREATED.value,
            "started_at": now.isoformat(),
            "approval_required": True,
            "steps": self._build_recovery_steps(context),
        }

    def _build_recovery_steps(self, context: RecoveryContext) -> list[dict]:
        """Build the 14-step recovery sequence."""
        steps = [
            {"step": 1, "name": "load_config", "description": "Load config and approval state"},
            {"step": 2, "name": "verify_clock", "description": "Verify clock synchronization"},
            {"step": 3, "name": "connect_qmt", "description": "Connect to QMT"},
            {"step": 4, "name": "query_broker_state", "description": "Query account/positions/orders/trades from QMT"},
            {"step": 5, "name": "load_local_state", "description": "Load local unfinished states"},
            {"step": 6, "name": "restore_reservations", "description": "Restore CashReservations"},
            {"step": 7, "name": "reconcile_orders", "description": "Order reconciliation"},
            {"step": 8, "name": "reconcile_trades", "description": "Trade reconciliation"},
            {"step": 9, "name": "reconcile_positions", "description": "Position reconciliation"},
            {"step": 10, "name": "check_external_events", "description": "Check for external manual events"},
            {"step": 11, "name": "rebuild_context", "description": "Rebuild DecisionSnapshot and Strategy context"},
            {"step": 12, "name": "establish_session", "description": "Establish RecoverySession"},
            {"step": 13, "name": "default_pause_open", "description": "Default to pause_open mode"},
            {"step": 14, "name": "wait_approval", "description": "Wait for human or rule approval to resume"},
        ]

        # Flag steps that need extra attention based on context
        if context.has_uncertain_orders:
            steps[6]["note"] = "Has uncertain orders — extra reconciliation needed"
        if context.has_position_mismatch:
            steps[8]["note"] = "Position mismatch detected — detailed comparison required"
        if context.has_external_events:
            steps[9]["note"] = "External events detected — manual confirmation required"
        if context.has_expired_reservations:
            steps[5]["note"] = "Expired reservations found — release before restoring"

        return steps

    async def execute_recovery_step(
        self,
        session_id: str,
        step_name: str,
    ) -> RecoveryStep:
        """Execute a single recovery step.

        In production, each step would have a concrete implementation.
        For now, returns a placeholder result.
        """
        return RecoveryStep(
            step_number=0,
            name=step_name,
            description=f"Executed {step_name}",
            status="completed",
            result="OK",
        )

    def determine_initial_mode(self, context: RecoveryContext) -> StrategyStatus:
        """Determine the initial strategy mode after recovery.

        Always defaults to pause_open (conservative).
        Live_running requires explicit human approval.
        """
        if context.has_external_events:
            return StrategyStatus.CLOSE_ONLY  # External events → close only
        if context.has_position_mismatch:
            return StrategyStatus.CLOSE_ONLY  # Position mismatch → close only
        return StrategyStatus.PAUSE_OPEN  # Default: pause open, wait for approval
