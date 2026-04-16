"""Portfolio state tracking for backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from hqmts.core.enums import Side
from hqmts.domain.bar import Bar


@dataclass
class Position:
    """Tracks a single instrument position."""

    instrument_id: str
    quantity: int = 0
    today_bought: int = 0
    average_cost: Decimal = Decimal("0")
    market_value: Decimal = Decimal("0")

    @property
    def sellable(self) -> int:
        """Shares available to sell (T+1 rule)."""
        return self.quantity - self.today_bought


@dataclass
class TradeRecord:
    """Record of a completed trade."""

    trade_id: str
    instrument_id: str
    side: str  # "buy" or "sell"
    price: Decimal
    quantity: int
    commission: Decimal
    stamp_tax: Decimal
    timestamp: datetime
    signal_id: str = ""


@dataclass
class DailyValue:
    """Portfolio value snapshot at end of a trading day."""

    trade_date: date
    cash: Decimal
    market_value: Decimal
    total_asset: Decimal
    position_value: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")


@dataclass
class PortfolioState:
    """Mutable portfolio state for a backtest run."""

    cash: Decimal
    initial_cash: Decimal
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[TradeRecord] = field(default_factory=list)
    daily_values: list[DailyValue] = field(default_factory=list)
    current_trade_date: date | None = None

    def get_or_create_position(self, instrument_id: str) -> Position:
        """Get existing position or create empty one."""
        if instrument_id not in self.positions:
            self.positions[instrument_id] = Position(instrument_id=instrument_id)
        return self.positions[instrument_id]

    def apply_fill(
        self,
        instrument_id: str,
        side: Side,
        fill_price: Decimal,
        fill_quantity: int,
        commission: Decimal,
        stamp_tax: Decimal,
        timestamp: datetime,
        signal_id: str = "",
    ) -> None:
        """Apply a fill to the portfolio state."""
        position = self.get_or_create_position(instrument_id)

        trade_amount = fill_price * Decimal(fill_quantity)

        if side == Side.BUY:
            position.quantity += fill_quantity
            position.today_bought += fill_quantity
            # Update average cost (weighted average)
            if position.quantity > 0:
                old_cost = position.average_cost * Decimal(position.quantity - fill_quantity)
                new_cost = fill_price * Decimal(fill_quantity)
                position.average_cost = (old_cost + new_cost) / Decimal(position.quantity)
            self.cash -= trade_amount + commission + stamp_tax
        else:
            position.quantity -= fill_quantity
            self.cash += trade_amount - commission - stamp_tax

        trade = TradeRecord(
            trade_id=f"T-{len(self.trades) + 1:06d}",
            instrument_id=instrument_id,
            side="buy" if side == Side.BUY else "sell",
            price=fill_price,
            quantity=fill_quantity,
            commission=commission,
            stamp_tax=stamp_tax,
            timestamp=timestamp,
            signal_id=signal_id,
        )
        self.trades.append(trade)

    def update_market_value(self, bars: list[Bar]) -> None:
        """Update market values for all positions using latest bar prices."""
        price_map: dict[str, Decimal] = {}
        for bar in bars:
            price_map[str(bar.instrument_id)] = bar.close

        self.update_market_value_from_prices(price_map)

    def update_market_value_from_prices(self, price_map: dict[str, Decimal]) -> None:
        """Update market values for all positions using a pre-built price map.

        O(1) per instrument instead of scanning all bars.
        """
        for iid, pos in self.positions.items():
            if iid in price_map:
                pos.market_value = price_map[iid] * Decimal(pos.quantity)

    def calculate_total_asset(self) -> Decimal:
        """Calculate total asset value (cash + positions market value)."""
        mv = sum(pos.market_value for pos in self.positions.values())
        return self.cash + mv

    def reset_daily_state(self) -> None:
        """Reset T+1 tracking at start of new trading day."""
        for pos in self.positions.values():
            pos.today_bought = 0

    def snapshot_daily(self, trade_date: date) -> DailyValue:
        """Take a daily snapshot of portfolio state."""
        total = self.calculate_total_asset()
        mv = sum(pos.market_value for pos in self.positions.values())

        dv = DailyValue(
            trade_date=trade_date,
            cash=self.cash,
            market_value=mv,
            total_asset=total,
        )
        self.daily_values.append(dv)
        return dv
