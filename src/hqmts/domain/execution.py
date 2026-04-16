"""ExecutionIntent and OrderRequest domain models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import OrderType, Side, TIF
from hqmts.core.types import (
    ActionId,
    AccountId,
    ExecutionIntentId,
    IdempotencyKey,
    InstrumentId,
    OrderRequestId,
    ReservationId,
    SignalId,
    StrategyInstanceId,
)


class ExecutionIntent(BaseModel):
    """Intermediate execution intent between Signal and OrderRequest (SAD 7.1).

    Represents a risk-checked, reservation-bound intention to execute.
    """

    execution_intent_id: ExecutionIntentId
    signal_id: SignalId
    strategy_instance_id: StrategyInstanceId
    account_id: AccountId
    instrument_id: InstrumentId
    side: Side
    target_quantity: int = Field(gt=0)
    reference_price: Decimal = Field(ge=0)
    reservation_id: ReservationId | None = None
    risk_check_id: str | None = None
    created_at: datetime

    model_config = {"frozen": True}


class OrderRequest(BaseModel):
    """Order submission request (PRD 9.5).

    Constraints:
    - All order requests must carry an idempotency key
    - Same action_id cannot submit duplicate intent orders
    """

    order_request_id: OrderRequestId
    signal_id: SignalId
    action_id: ActionId
    account_id: AccountId
    instrument_id: InstrumentId
    side: Side
    order_type: OrderType = OrderType.LIMIT
    price: Decimal = Field(ge=0)
    quantity: int = Field(gt=0)
    tif: TIF = TIF.GTC
    submit_time: datetime
    idempotency_key: IdempotencyKey
    execution_intent_id: ExecutionIntentId | None = None
    reservation_id: ReservationId | None = None

    model_config = {"frozen": True}
