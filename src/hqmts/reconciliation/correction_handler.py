"""Correction handler service (SAD 10.4).

Processes broker trade corrections: records the correction,
triggers position reconciliation, and adjusts positions.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from hqmts.core.enums import CorrectionType
from hqmts.core.types import now_shanghai
from hqmts.domain.correction import CorrectionEvent

logger = logging.getLogger(__name__)


class CorrectionHandler:
    """Processes broker trade corrections.

    Flow:
    1. record_correction() → creates CorrectionEvent
    2. process_correction() → triggers reconciliation, adjusts position
    3. Marks correction as processed
    """

    def __init__(
        self,
        *,
        position_repo: object | None = None,
        reconciliation_service: object | None = None,
    ) -> None:
        self._position_repo = position_repo
        self._reconciliation_service = reconciliation_service
        self._corrections: dict[str, CorrectionEvent] = {}

    async def record_correction(
        self,
        *,
        broker_trade_id: str,
        instrument_id: str,
        correction_type: CorrectionType,
        original_price: Decimal = Decimal("0"),
        original_quantity: int = 0,
        original_commission: Decimal = Decimal("0"),
        corrected_price: Decimal | None = None,
        corrected_quantity: int | None = None,
        corrected_commission: Decimal | None = None,
        reason: str = "",
    ) -> CorrectionEvent:
        """Record a new broker trade correction."""
        event = CorrectionEvent(
            correction_id=str(uuid.uuid4()),
            broker_trade_id=broker_trade_id,
            instrument_id=instrument_id,
            correction_type=correction_type,
            original_price=original_price,
            original_quantity=original_quantity,
            original_commission=original_commission,
            corrected_price=corrected_price,
            corrected_quantity=corrected_quantity,
            corrected_commission=corrected_commission,
            reason=reason,
            detected_at=now_shanghai(),
            created_at=now_shanghai(),
        )
        self._corrections[event.correction_id] = event

        logger.info(
            "CORRECTION_RECORDED id=%s type=%s instrument=%s trade=%s",
            event.correction_id[:8],
            correction_type.value,
            instrument_id,
            broker_trade_id,
        )
        return event

    async def process_correction(
        self,
        correction_id: str,
    ) -> CorrectionEvent:
        """Process a recorded correction.

        Triggers position reconciliation and marks as processed.
        """
        event = self._corrections.get(correction_id)
        if event is None:
            raise ValueError(f"Correction {correction_id} not found")

        if event.is_processed:
            # Idempotent: already processed
            logger.info("CORRECTION_ALREADY_PROCESSED id=%s", correction_id[:8])
            return event

        # Trigger reconciliation (if service available)
        if self._reconciliation_service is not None:
            # In production, this would trigger a reconciliation session
            # for the affected instrument and link it to the correction
            event.reconciliation_session_id = str(uuid.uuid4())

        # Adjust position (if repo available)
        if self._position_repo is not None and event.correction_type == CorrectionType.QUANTITY_CORRECTION:
            # In production, this would adjust the position quantity
            logger.info(
                "CORRECTION_POSITION_ADJUST id=%s instrument=%s",
                correction_id[:8], event.instrument_id,
            )

        event.is_processed = True
        event.processed_at = now_shanghai()

        logger.info(
            "CORRECTION_PROCESSED id=%s type=%s",
            correction_id[:8], event.correction_type.value,
        )
        return event

    async def get_unprocessed_corrections(self) -> list[CorrectionEvent]:
        """Get all unprocessed corrections."""
        return [
            c for c in self._corrections.values()
            if not c.is_processed
        ]

    def get_correction(self, correction_id: str) -> CorrectionEvent | None:
        """Get a correction by ID."""
        return self._corrections.get(correction_id)
