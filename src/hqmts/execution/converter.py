"""Signal → Intent → Order conversion (SAD Section 17).

Full pipeline:
Signal → DecisionSnapshot validation → Pre-Trade Risk → Cash Reservation →
ExecutionIntent → Target-to-Order conversion → Final Pre-Submit Check →
OrderRequest
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from hqmts.core.enums import (
    FinalCheckResult,
    OrderType,
    RiskResultType,
    Side,
    SignalType,
    StrategyStatus,
    TIF,
)
from hqmts.core.exceptions import (
    ExpiredSignalError,
    IncompleteSnapshotError,
    MissingDecisionSnapshotError,
    StalePriceError,
)
from hqmts.core.types import (
    ActionId,
    ExecutionIntentId,
    IdempotencyKey,
    OrderRequestId,
)
from hqmts.domain.execution import ExecutionIntent, OrderRequest
from hqmts.domain.risk import RiskCheckResult
from hqmts.domain.signal import Signal
from hqmts.risk.engine import RiskContext, RiskEngine
from hqmts.risk.final_check import FinalPreSubmitCheck, FinalCheckContext
from hqmts.core.types import now_shanghai


class SignalConverter:
    """Converts validated signals to execution intents and order requests."""

    def __init__(
        self,
        risk_engine: RiskEngine,
        final_check: FinalPreSubmitCheck,
        stale_price_threshold_seconds: int = 30,
    ) -> None:
        self._risk_engine = risk_engine
        self._final_check = final_check
        self._stale_threshold = stale_price_threshold_seconds

    async def validate_signal_for_live(self, signal: Signal) -> None:
        """Validate signal has all required bindings for Live execution."""
        if signal.is_expired():
            raise ExpiredSignalError(
                signal_id=signal.signal_id,
                valid_until=str(signal.valid_until),
            )

        if not signal.has_decision_binding():
            raise MissingDecisionSnapshotError(
                signal_id=signal.signal_id,
            )

    async def run_pre_trade_risk(
        self,
        signal: Signal,
        context: RiskContext,
    ) -> RiskCheckResult:
        """Run pre-trade risk checks on a signal."""
        # Copy context to avoid mutating the caller's object
        ctx = context.model_copy(update={"signal_id": signal.signal_id})
        return await self._risk_engine.evaluate(ctx)

    async def create_execution_intent(
        self,
        signal: Signal,
        account_id: str,
        reference_price: Decimal,
        quantity: int,
        reservation_id: str | None = None,
        risk_check_id: str | None = None,
    ) -> ExecutionIntent:
        """Create an ExecutionIntent from a validated signal."""
        side = self.determine_side(signal)
        return ExecutionIntent(
            execution_intent_id=ExecutionIntentId(str(uuid.uuid4())),
            signal_id=signal.signal_id,
            strategy_instance_id=signal.strategy_instance_id,
            account_id=account_id,  # type: ignore
            instrument_id=signal.instrument_id,
            side=side,
            target_quantity=quantity,
            reference_price=reference_price,
            reservation_id=reservation_id,  # type: ignore
            risk_check_id=risk_check_id,
            created_at=now_shanghai(),
        )

    async def convert_to_order_request(
        self,
        intent: ExecutionIntent,
        order_type: OrderType = OrderType.LIMIT,
        tif: TIF = TIF.GTC,
    ) -> OrderRequest:
        """Convert ExecutionIntent to OrderRequest after Final Pre-Submit Check."""
        now = now_shanghai()
        return OrderRequest(
            order_request_id=OrderRequestId(str(uuid.uuid4())),
            signal_id=intent.signal_id,
            action_id=ActionId(str(uuid.uuid4())),
            account_id=intent.account_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            order_type=order_type,
            price=intent.reference_price,
            quantity=intent.target_quantity,
            tif=tif,
            submit_time=now,
            idempotency_key=IdempotencyKey(
                f"{intent.signal_id}:{intent.instrument_id}:{now.isoformat()}"
            ),
            execution_intent_id=intent.execution_intent_id,
            reservation_id=intent.reservation_id,
        )

    @staticmethod
    def determine_side(signal: Signal) -> Side:
        """Map signal type to order side."""
        side_map = {
            SignalType.OPEN_LONG: Side.BUY,
            SignalType.CLOSE_LONG: Side.SELL,
            SignalType.OPEN_SHORT: Side.SELL,
            SignalType.CLOSE_SHORT: Side.BUY,
            SignalType.FLATTEN: Side.SELL,
        }
        if signal.signal_type not in side_map:
            raise ValueError(f"Cannot determine side for signal type: {signal.signal_type}")
        return side_map[signal.signal_type]
