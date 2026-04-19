"""Account domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.types import AccountId


class Account(BaseModel):
    """Account state (PRD 9.9).

    Tracks account balance, risk status, and P&L.
    """

    account_id: AccountId
    total_asset: Decimal = Field(ge=0)
    available_cash: Decimal = Field(ge=0)
    frozen_cash: Decimal = Field(default=Decimal("0"), ge=0)
    market_value: Decimal = Field(default=Decimal("0"), ge=0)
    pnl_intraday: Decimal = Decimal("0")
    drawdown_intraday: Decimal = Decimal("0")
    risk_status: str = "normal"  # normal, warning, danger
    currency: str = "CNY"
    updated_at: datetime

    @property
    def position_ratio(self) -> Decimal:
        """Current position ratio (0.0 - 1.0)."""
        if self.total_asset == 0:
            return Decimal("0")
        return self.market_value / self.total_asset
