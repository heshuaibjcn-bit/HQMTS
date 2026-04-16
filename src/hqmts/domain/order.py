"""Order domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import OrderStatus, Side
from hqmts.core.types import BrokerOrderId, OrderId, OrderRequestId


class Order(BaseModel):
    """Broker-accepted order (PRD 9.6, SAD 15.1).

    Order status follows the state machine defined in SAD 15.1.
    """

    order_id: OrderId
    order_request_id: OrderRequestId | None = None
    broker_order_id: BrokerOrderId | None = None
    account_id: str = ""
    instrument_id: str
    side: Side
    price: Decimal = Field(ge=0)
    quantity: int = Field(gt=0)
    status: OrderStatus = OrderStatus.CREATED
    submitted_time: datetime | None = None
    updated_time: datetime | None = None
    filled_quantity: int = Field(default=0, ge=0)
    avg_fill_price: Decimal = Field(default=Decimal("0"), ge=0)
    reject_reason: str = ""
    created_at: datetime
    updated_at: datetime

    @property
    def unfilled_quantity(self) -> int:
        """Remaining unfilled quantity."""
        return self.quantity - self.filled_quantity

    @property
    def is_terminal(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        )

    @property
    def is_active(self) -> bool:
        """Check if order is still active (may receive fills)."""
        return self.status in (
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
        )
