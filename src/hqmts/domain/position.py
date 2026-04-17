"""Position domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.types import AccountId, InstrumentId


class Position(BaseModel):
    """Position state (PRD 9.8).

    Key constraints:
    - total_quantity vs available_quantity must be distinguished
    - A-stock T+1: available_quantity may be less than total_quantity on buy day
    """

    account_id: AccountId
    instrument_id: InstrumentId
    total_quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    frozen_quantity: int = Field(default=0, ge=0)
    cost_price: Decimal = Field(ge=0)
    market_value: Decimal = Field(default=Decimal("0"), ge=0)
    market_price: Decimal = Field(default=Decimal("0"), ge=0)
    realized_pnl: Decimal = Decimal("0")
    strategy_instance_id: str = ""
    updated_at: datetime

    @property
    def is_flat(self) -> bool:
        """Check if position is flat (no holding)."""
        return self.total_quantity == 0

    @property
    def unrealized_pnl(self) -> Decimal:
        """Unrealized profit/loss."""
        if self.market_price > 0:
            return (self.market_price - self.cost_price) * self.total_quantity
        return self.market_value - (self.cost_price * self.total_quantity)

    @classmethod
    def serialization_key(cls, entity_id: str) -> str:
        return f"position:{entity_id}"
