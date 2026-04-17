"""Execution orchestration service.

Coordinates the full signal → order pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from hqmts.core.enums import FinalCheckResult, OrderStatus, RiskResultType
from hqmts.core.exceptions import RiskRejectError
from hqmts.domain.execution import ExecutionIntent, OrderRequest
from hqmts.domain.signal import Signal
from hqmts.execution.converter import SignalConverter
from hqmts.execution.reject_handler import RejectHandler
from hqmts.reservation.manager import ReservationManager
from hqmts.risk.engine import RiskContext, RiskEngine
from hqmts.risk.final_check import FinalCheckContext, FinalPreSubmitCheck

logger = logging.getLogger(__name__)


class ExecutionService:
    """Orchestrates the full execution pipeline:

    Signal → Risk Check → Reservation → Intent → Final Check → OrderRequest
    """

    def __init__(
        self,
        risk_engine: RiskEngine,
        final_check: FinalPreSubmitCheck,
        reservation_manager: ReservationManager,
        converter: SignalConverter,
        reject_handler: RejectHandler,
    ) -> None:
        self._risk_engine = risk_engine
        self._final_check = final_check
        self._reservation_manager = reservation_manager
        self._converter = converter
        self._reject_handler = reject_handler

    async def process_signal(
        self,
        signal: Signal,
        account_id: str,
        reference_price: Decimal,
        target_quantity: int,
        risk_context: RiskContext,
        final_check_context: FinalCheckContext,
    ) -> ExecutionIntent | OrderRequest | None:
        """Process a signal through the full execution pipeline.

        Returns OrderRequest if successful, None if rejected/delayed.
        Raises RiskRejectError on risk rejection.
        Raises ForceFlattenError on force_flatten (caller must handle).
        """
        # Step 1: Validate signal
        await self._converter.validate_signal_for_live(signal)

        # Step 2: Pre-trade risk
        risk_result = await self._converter.run_pre_trade_risk(signal, risk_context)
        if risk_result.result_type == RiskResultType.REJECT:
            raise RiskRejectError(
                risk_result.reject_reason,
                risk_result.triggered_rules,
            )
        if risk_result.result_type == RiskResultType.FORCE_FLATTEN:
            # Force flatten must be handled by caller — do not continue pipeline
            from hqmts.core.exceptions import ForceFlattenError
            raise ForceFlattenError(
                reason=risk_result.reject_reason,
                triggered_rules=risk_result.triggered_rules,
            )
        if risk_result.result_type == RiskResultType.DELAY:
            # Delay means this signal should be retried later, not executed now
            return None

        # Adjust quantity if resized
        effective_quantity = target_quantity
        if risk_result.result_type == RiskResultType.RESIZE and risk_result.resized_quantity:
            effective_quantity = risk_result.resized_quantity

        # Step 3: Cash reservation (for opening positions)
        reservation_id = None
        opening_types = {"open_long", "open_short"}
        if signal.signal_type in opening_types and reference_price > 0:
            order_value = reference_price * effective_quantity
            reservation = await self._reservation_manager.reserve(
                account_id=account_id,  # type: ignore
                strategy_instance_id=signal.strategy_instance_id,
                amount=order_value,
                signal_id=signal.signal_id,
                available_cash=final_check_context.account_available_cash,
            )
            reservation_id = reservation.reservation_id

        # Step 4-6: Create intent, final check, order request
        # Wrapped in try/except to release reservation on any failure
        try:
            intent = await self._converter.create_execution_intent(
                signal=signal,
                account_id=account_id,
                reference_price=reference_price,
                quantity=effective_quantity,
                reservation_id=reservation_id,
                risk_check_id=risk_result.risk_check_id,
            )

            # Step 5: Final Pre-Submit Check — populate context from intent
            final_check_context.price = intent.reference_price
            final_check_context.quantity = intent.target_quantity
            final_check_context.side = intent.side.value
            final_check_context.instrument_id = intent.instrument_id
            final_result = await self._final_check.execute(final_check_context)
            if final_result.result != FinalCheckResult.ALLOW:
                if reservation_id:
                    await self._reservation_manager.release(
                        reservation_id,
                        reason=f"Final check failed: {final_result.reason}",
                    )
                return None

            # Step 6: Create order request
            order_request = await self._converter.convert_to_order_request(intent)
            return order_request
        except Exception:
            # Release reservation on any unexpected failure
            if reservation_id:
                await self._reservation_manager.release(
                    reservation_id,
                    reason="Pipeline exception during execution",
                )
            raise

    async def handle_fill(
        self,
        reservation_id: str | None,
        fill_amount: Decimal,
        order_id: str,
    ) -> None:
        """Handle order fill by consuming the cash reservation.

        Called by the QMT callback handler when an order is filled.
        Transitions reservation: active → partially_consumed / fully_consumed.
        """
        if not reservation_id:
            return
        try:
            await self._reservation_manager.consume(reservation_id, fill_amount)
            logger.info(
                "RESERVATION_CONSUMED order=%s reservation=%s amount=%s",
                order_id, reservation_id, fill_amount,
            )
        except Exception as exc:
            logger.warning(
                "RESERVATION_CONSUME_FAILED order=%s reservation=%s error=%s",
                order_id, reservation_id, exc,
            )

    async def handle_order_failed(
        self,
        reservation_id: str | None,
        order_id: str,
        reason: str,
    ) -> None:
        """Handle order rejection/cancellation by releasing the reservation.

        Called by the QMT callback handler when an order fails.
        Transitions reservation: active → released.
        """
        if not reservation_id:
            return
        try:
            await self._reservation_manager.release(reservation_id, reason=reason)
            logger.info(
                "RESERVATION_RELEASED order=%s reservation=%s reason=%s",
                order_id, reservation_id, reason,
            )
        except Exception as exc:
            logger.warning(
                "RESERVATION_RELEASE_FAILED order=%s reservation=%s error=%s",
                order_id, reservation_id, exc,
            )
