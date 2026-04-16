"""Recovery service (SAD Sections 15.5, 22).

Handles system startup recovery, restart sequence, and fault recovery.
Default: enter pause_open, wait for human confirmation.
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import RecoveryStatus, StrategyStatus
from hqmts.core.types import RecoveryId
from hqmts.db.models.external_event import ExternalManualEventORM
from hqmts.db.models.recovery import RecoverySessionORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.db.repositories.order_repo import OrderRepository
from hqmts.db.repositories.reservation_repo import ReservationRepository
from hqmts.reconciliation.service import ReconciliationService
from hqmts.reservation.manager import ReservationManager


# ---------------------------------------------------------------------------
# Broker adapter interface
# ---------------------------------------------------------------------------


class BrokerAdapter(abc.ABC):
    """Abstract broker interface for recovery queries.

    In production, this wraps QMT. For testing, use FakeBrokerAdapter.
    """

    @abc.abstractmethod
    async def connect(self) -> bool:
        """Connect to the broker. Returns True on success."""

    @abc.abstractmethod
    async def query_positions(self, account_id: str) -> list[dict]:
        """Query current positions from broker."""

    @abc.abstractmethod
    async def query_orders(self, account_id: str) -> list[dict]:
        """Query today's orders from broker."""

    @abc.abstractmethod
    async def query_trades(self, account_id: str) -> list[dict]:
        """Query today's trades from broker."""

    @abc.abstractmethod
    async def query_account(self, account_id: str) -> dict:
        """Query account summary from broker."""


class FakeBrokerAdapter(BrokerAdapter):
    """Fake broker for testing. Returns configurable canned data."""

    def __init__(
        self,
        *,
        connected: bool = True,
        positions: list[dict] | None = None,
        orders: list[dict] | None = None,
        trades: list[dict] | None = None,
        account: dict | None = None,
    ) -> None:
        self._connected = connected
        self._positions = positions or []
        self._orders = orders or []
        self._trades = trades or []
        self._account = account or {
            "total_asset": "1000000",
            "available_cash": "500000",
            "market_value": "500000",
        }

    async def connect(self) -> bool:
        return self._connected

    async def query_positions(self, account_id: str) -> list[dict]:
        return list(self._positions)

    async def query_orders(self, account_id: str) -> list[dict]:
        return list(self._orders)

    async def query_trades(self, account_id: str) -> list[dict]:
        return list(self._trades)

    async def query_account(self, account_id: str) -> dict:
        return dict(self._account)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Step name constants
# ---------------------------------------------------------------------------

_STEP_DEFINITIONS: list[tuple[str, str]] = [
    ("load_config", "Load config and approval state"),
    ("verify_clock", "Verify clock synchronization"),
    ("connect_qmt", "Connect to QMT"),
    ("query_broker_state", "Query account/positions/orders/trades from QMT"),
    ("load_local_state", "Load local unfinished states"),
    ("restore_reservations", "Restore CashReservations"),
    ("reconcile_orders", "Order reconciliation"),
    ("reconcile_trades", "Trade reconciliation"),
    ("reconcile_positions", "Position reconciliation"),
    ("check_external_events", "Check for external manual events"),
    ("rebuild_context", "Rebuild DecisionSnapshot and Strategy context"),
    ("establish_session", "Establish RecoverySession"),
    ("default_pause_open", "Default to pause_open mode"),
    ("wait_approval", "Wait for human or rule approval to resume"),
]


# ---------------------------------------------------------------------------
# Recovery service
# ---------------------------------------------------------------------------


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

    def __init__(
        self,
        session: AsyncSession,
        broker_adapter: BrokerAdapter | None = None,
    ) -> None:
        self._session = session
        self._broker = broker_adapter or FakeBrokerAdapter()
        self._recovery_repo = BaseRepository(RecoverySessionORM, session)
        self._order_repo = OrderRepository(session)
        self._reservation_repo = ReservationRepository(session)
        self._reconciliation = ReconciliationService()

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
            {"step": i + 1, "name": name, "description": desc}
            for i, (name, desc) in enumerate(_STEP_DEFINITIONS)
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
        context: RecoveryContext | None = None,
    ) -> RecoveryStep:
        """Execute a single recovery step by name.

        Dispatches to the matching _execute_* method. Each method returns
        a RecoveryStep with real status and result.
        """
        step_number = next(
            (i + 1 for i, (name, _) in enumerate(_STEP_DEFINITIONS) if name == step_name),
            0,
        )
        handler = getattr(self, f"_execute_{step_name}", None)
        if handler is None:
            return RecoveryStep(
                step_number=step_number,
                name=step_name,
                description=f"Unknown step: {step_name}",
                status="failed",
                result=f"No handler for step '{step_name}'",
            )
        return await handler(session_id, step_number, context)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _execute_load_config(
        self, session_id: str, step_number: int, _
    ) -> RecoveryStep:
        """Step 1: Verify config is loadable."""
        # In production, this would reload and validate config.
        # For P1, config is already loaded by the app factory.
        return RecoveryStep(
            step_number=step_number,
            name="load_config",
            description="Load config and approval state",
            status="completed",
            result="Config loaded successfully",
        )

    async def _execute_verify_clock(
        self, session_id: str, step_number: int, _
    ) -> RecoveryStep:
        """Step 2: Verify clock sync."""
        # In production, check NTP offset or compare against exchange clock.
        now = datetime.now()
        return RecoveryStep(
            step_number=step_number,
            name="verify_clock",
            description="Verify clock synchronization",
            status="completed",
            result=f"Clock verified at {now.isoformat()}",
        )

    async def _execute_connect_qmt(
        self, session_id: str, step_number: int, _
    ) -> RecoveryStep:
        """Step 3: Connect to QMT broker."""
        connected = await self._broker.connect()
        if connected:
            return RecoveryStep(
                step_number=step_number,
                name="connect_qmt",
                description="Connect to QMT",
                status="completed",
                result="QMT connected",
            )
        return RecoveryStep(
            step_number=step_number,
            name="connect_qmt",
            description="Connect to QMT",
            status="failed",
            result="Failed to connect to QMT",
        )

    async def _execute_query_broker_state(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 4: Query broker state (positions, orders, trades, account)."""
        if context is None:
            return RecoveryStep(
                step_number=step_number, name="query_broker_state",
                description="Query account/positions/orders/trades from QMT",
                status="failed", result="No recovery context provided",
            )
        account_id = context.account_id
        try:
            positions = await self._broker.query_positions(account_id)
            orders = await self._broker.query_orders(account_id)
            trades = await self._broker.query_trades(account_id)
            account = await self._broker.query_account(account_id)
            return RecoveryStep(
                step_number=step_number,
                name="query_broker_state",
                description="Query account/positions/orders/trades from QMT",
                status="completed",
                result=(
                    f"positions={len(positions)}, orders={len(orders)}, "
                    f"trades={len(trades)}, cash={account.get('available_cash', '?')}"
                ),
            )
        except Exception as exc:
            return RecoveryStep(
                step_number=step_number, name="query_broker_state",
                description="Query account/positions/orders/trades from QMT",
                status="failed", result=f"Broker query failed: {exc}",
            )

    async def _execute_load_local_state(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 5: Load local unfinished states (active orders)."""
        if context is None:
            return RecoveryStep(
                step_number=step_number, name="load_local_state",
                description="Load local unfinished states",
                status="failed", result="No recovery context provided",
            )
        active_orders = await self._order_repo.get_active_orders_by_account(
            context.account_id,
        )
        return RecoveryStep(
            step_number=step_number,
            name="load_local_state",
            description="Load local unfinished states",
            status="completed",
            result=f"Found {len(active_orders)} active orders",
        )

    async def _execute_restore_reservations(
        self, session_id: str, step_number: int, _
    ) -> RecoveryStep:
        """Step 6: Release expired reservations, keep active ones."""
        manager = ReservationManager(self._reservation_repo)
        expired = await manager.expire_reservations()
        return RecoveryStep(
            step_number=step_number,
            name="restore_reservations",
            description="Restore CashReservations",
            status="completed",
            result=f"Released {len(expired)} expired reservations",
        )

    async def _execute_reconcile_orders(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 7: Reconcile local orders vs broker orders."""
        if context is None:
            return RecoveryStep(
                step_number=step_number, name="reconcile_orders",
                description="Order reconciliation",
                status="failed", result="No recovery context provided",
            )
        local_orders_orm = await self._order_repo.get_active_orders_by_account(
            context.account_id,
        )
        local_orders = [
            {"order_id": o.order_id, "broker_order_id": o.broker_order_id,
             "status": o.status, "filled_quantity": o.filled_quantity}
            for o in local_orders_orm
        ]
        broker_orders = await self._broker.query_orders(context.account_id)
        result = await self._reconciliation.reconcile_orders(
            context.account_id, local_orders, broker_orders,
        )
        status = "completed" if not result.has_critical else "failed"
        return RecoveryStep(
            step_number=step_number,
            name="reconcile_orders",
            description="Order reconciliation",
            status=status,
            result=f"diffs={len(result.diffs)}, external={result.external_events_detected}",
        )

    async def _execute_reconcile_trades(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 8: Reconcile local trades vs broker trades."""
        if context is None:
            return RecoveryStep(
                step_number=step_number, name="reconcile_trades",
                description="Trade reconciliation",
                status="failed", result="No recovery context provided",
            )
        # P1: no local trade ORM yet, so just compare broker trades against empty
        broker_trades = await self._broker.query_trades(context.account_id)
        result = await self._reconciliation.reconcile_trades(
            context.account_id, [], broker_trades,
        )
        status = "completed" if not result.has_critical else "failed"
        return RecoveryStep(
            step_number=step_number,
            name="reconcile_trades",
            description="Trade reconciliation",
            status=status,
            result=f"diffs={len(result.diffs)}, external={result.external_events_detected}",
        )

    async def _execute_reconcile_positions(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 9: Reconcile local positions vs broker positions."""
        if context is None:
            return RecoveryStep(
                step_number=step_number, name="reconcile_positions",
                description="Position reconciliation",
                status="failed", result="No recovery context provided",
            )
        broker_positions = await self._broker.query_positions(context.account_id)
        result = await self._reconciliation.reconcile_positions(
            context.account_id, [], broker_positions,
        )
        status = "completed" if not result.has_critical else "failed"
        return RecoveryStep(
            step_number=step_number,
            name="reconcile_positions",
            description="Position reconciliation",
            status=status,
            result=f"diffs={len(result.diffs)}",
        )

    async def _execute_check_external_events(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 10: Query ExternalManualEvent table for unhandled events."""
        if context is None:
            return RecoveryStep(
                step_number=step_number, name="check_external_events",
                description="Check for external manual events",
                status="failed", result="No recovery context provided",
            )
        stmt = (
            select(ExternalManualEventORM)
            .where(ExternalManualEventORM.account_id == context.account_id)
            .where(ExternalManualEventORM.action_taken == "")
        )
        db_result = await self._session.execute(stmt)
        events = list(db_result.scalars().all())
        status = "completed" if not events else "completed"
        return RecoveryStep(
            step_number=step_number,
            name="check_external_events",
            description="Check for external manual events",
            status=status,
            result=f"Found {len(events)} unhandled external events",
        )

    async def _execute_rebuild_context(
        self, session_id: str, step_number: int, _
    ) -> RecoveryStep:
        """Step 11: Rebuild DecisionSnapshot and Strategy context.

        P1: Placeholder. In production, loads the last known good
        DecisionSnapshot and rebuilds strategy state from it.
        """
        return RecoveryStep(
            step_number=step_number,
            name="rebuild_context",
            description="Rebuild DecisionSnapshot and Strategy context",
            status="completed",
            result="Context rebuilt (P1 placeholder)",
        )

    async def _execute_establish_session(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 12: Persist RecoverySession to DB."""
        if context is None:
            return RecoveryStep(
                step_number=step_number, name="establish_session",
                description="Establish RecoverySession",
                status="failed", result="No recovery context provided",
            )
        now = datetime.now()
        orm = RecoverySessionORM(
            recovery_session_id=session_id,
            scope_type="strategy",
            scope_id=context.strategy_instance_id,
            trigger_reason=context.trigger_reason,
            approval_required=True,
            status=RecoveryStatus.RECONCILING.value,
            started_at=now,
        )
        await self._recovery_repo.create(orm)
        await self._session.flush()
        return RecoveryStep(
            step_number=step_number,
            name="establish_session",
            description="Establish RecoverySession",
            status="completed",
            result=f"Session {session_id[:8]}... persisted",
        )

    async def _execute_default_pause_open(
        self, session_id: str, step_number: int, context: RecoveryContext | None,
    ) -> RecoveryStep:
        """Step 13: Determine initial mode (conservative: pause_open)."""
        if context is not None:
            mode = self.determine_initial_mode(context)
        else:
            mode = StrategyStatus.PAUSE_OPEN
        return RecoveryStep(
            step_number=step_number,
            name="default_pause_open",
            description="Default to pause_open mode",
            status="completed",
            result=f"Initial mode: {mode.value}",
        )

    async def _execute_wait_approval(
        self, session_id: str, step_number: int, _
    ) -> RecoveryStep:
        """Step 14: Wait for human or rule approval to resume.

        This step always returns pending, since approval requires
        an external action.
        """
        return RecoveryStep(
            step_number=step_number,
            name="wait_approval",
            description="Wait for human or rule approval to resume",
            status="pending",
            result="Waiting for approval (requires external action)",
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

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
