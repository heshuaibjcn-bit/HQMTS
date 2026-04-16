"""Trade domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.types import BrokerTradeId, InstrumentId, OrderId, TradeId


class Trade(BaseModel):
    """Execution fill record (PRD 9.7, SAD 15.2).

    Idempotency: broker_trade_id is the dedup key.
    Trade core fields are immutable once confirmed.
    Corrections use CorrectionEvent, not Trade mutation.
    """

    trade_id: TradeId
    order_id: OrderId
    instrument_id: InstrumentId
    trade_time: datetime
    trade_price: Decimal = Field(ge=0)
    trade_quantity: int = Field(gt=0)
    commission: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    broker_trade_id: BrokerTradeId | None = None
    created_at: datetime

    model_config = {"frozen": True}

    @property
    def trade_amount(self) -> Decimal:
        """Total trade amount (price * quantity)."""
        return self.trade_price * self.trade_quantity

    @property
    def total_cost(self) -> Decimal:
        """Total cost including commission and tax."""
        return self.trade_amount + self.commission + self.tax
