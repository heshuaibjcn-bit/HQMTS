"""ExternalManualEvent domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import Side
from hqmts.core.types import AccountId, ExternalEventId, InstrumentId, OrderId


class ExternalManualEvent(BaseModel):
    """External manual trading event detected in the account (SAD 7.5, 21).

    Triggers:
    - Manual order placed via QMT
    - Orders from other systems
    - Broker corrections
    - Unknown trades not matching any internal OrderRequest

    System response:
    - Record event
    - Reconcile position/account
    - Strategy enters at least pause_open
    - Requires human confirmation to resume live_running
    """

    external_event_id: ExternalEventId
    account_id: AccountId
    event_type: str  # manual_buy, manual_sell, manual_cancel, broker_correction, unknown_trade
    broker_order_id: str | None = None
    broker_trade_id: str | None = None
    instrument_id: InstrumentId | None = None
    side: Side | None = None
    quantity: int | None = None
    price: Decimal | None = None
    detected_at: datetime
    source_confidence: str = "high"  # high, medium, low
    linked_internal_order_id: OrderId | None = None
    action_taken: str = ""  # pause_open, close_only, reconciling
    audit_note: str = ""
