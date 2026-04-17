"""CorrectionEvent domain model (SAD 10.4).

Broker trade corrections for A-share markets. When the exchange/broker
sends a correction to a previously reported fill, this model records
the correction details and links it to the reconciliation process.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import CorrectionType
from hqmts.core.types import CorrectionEventId, InstrumentId
from hqmts.core.types import now_shanghai


class CorrectionEvent(BaseModel):
    """Broker trade correction record.

    Tracks price, quantity, and commission corrections from
    the exchange or broker. Links to reconciliation for follow-up.
    """

    correction_id: CorrectionEventId
    broker_trade_id: str
    instrument_id: InstrumentId
    correction_type: CorrectionType
    original_price: Decimal = Decimal("0")
    original_quantity: int = 0
    original_commission: Decimal = Decimal("0")
    corrected_price: Decimal | None = None
    corrected_quantity: int | None = None
    corrected_commission: Decimal | None = None
    reason: str = ""
    reconciliation_session_id: str = ""
    is_processed: bool = False
    detected_at: datetime = Field(default_factory=now_shanghai)
    processed_at: datetime | None = None
    created_at: datetime = Field(default_factory=now_shanghai)

    model_config = {"frozen": False}  # Mutable for processing updates
