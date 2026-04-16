"""BacktestOrder: richer order specification for backtest strategies."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from hqmts.core.enums import Side


@dataclass(frozen=True)
class BacktestOrder:
    """Order emitted by a backtest strategy.

    Extends the basic Signal with order-type, stop-loss, and take-profit.
    quantity=0 means "all available" for sell orders (resolved by matcher).
    """

    instrument_id: str
    side: Side
    quantity: int = 0
    order_type: str = "market"  # "market" | "limit"
    limit_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    signal_id: str = ""
    reason_code: str = ""
