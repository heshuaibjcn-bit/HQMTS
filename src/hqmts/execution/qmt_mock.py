"""Mock QMT adapter for testing the execution pipeline (FR-LIVE-001 scaffold).

Provides a configurable mock that simulates QMT broker behavior without
requiring actual QMT access. Supports failure injection and partial fills.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from hqmts.core.types import now_shanghai


@dataclass
class AccountSnapshot:
    """Mock account state from QMT."""

    account_id: str
    total_asset: Decimal
    available_cash: Decimal
    frozen_cash: Decimal
    market_value: Decimal
    currency: str = "CNY"


@dataclass
class PositionSnapshot:
    """Mock position from QMT."""

    instrument_id: str
    quantity: int
    available_quantity: int
    cost_price: Decimal
    market_price: Decimal
    unrealized_pnl: Decimal


@dataclass
class OrderSnapshot:
    """Mock order from QMT."""

    broker_order_id: str
    instrument_id: str
    side: str
    order_type: str
    price: Decimal
    quantity: int
    filled_quantity: int
    status: str
    submit_time: datetime


@dataclass
class FillStatus:
    """Fill status for a submitted order."""

    broker_order_id: str
    filled_quantity: int
    filled_price: Decimal
    status: str  # pending, partial, filled, canceled, rejected


@dataclass
class _MockOrder:
    """Internal mock order state."""

    broker_order_id: str
    instrument_id: str
    side: str
    order_type: str
    price: Decimal
    quantity: int
    filled_quantity: int = 0
    filled_price: Decimal = Decimal("0")
    status: str = "pending"
    submit_time: datetime = field(default_factory=now_shanghai)


class MockQMTAdapter:
    """Mock QMT adapter for testing.

    Supports:
    - Connect/disconnect lifecycle
    - Account and position queries
    - Order submission, cancellation
    - Fill status queries
    - Configurable failure injection
    """

    def __init__(
        self,
        account_id: str = "mock-account-001",
        initial_cash: Decimal = Decimal("1000000"),
        fail_submit: bool = False,
        partial_fill: bool = False,
    ) -> None:
        self._connected = False
        self._fail_submit = fail_submit
        self._partial_fill = partial_fill

        # Mock state
        self._account = AccountSnapshot(
            account_id=account_id,
            total_asset=initial_cash,
            available_cash=initial_cash,
            frozen_cash=Decimal("0"),
            market_value=Decimal("0"),
        )
        self._positions: dict[str, PositionSnapshot] = {}
        self._orders: dict[str, _MockOrder] = {}

    def connect(self) -> bool:
        """Connect to mock QMT."""
        self._connected = True
        return True

    def disconnect(self) -> bool:
        """Disconnect from mock QMT."""
        self._connected = False
        return True

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def query_account(self) -> AccountSnapshot:
        """Query account state."""
        if not self._connected:
            raise RuntimeError("QMT adapter not connected")
        return self._account

    def query_positions(self) -> list[PositionSnapshot]:
        """Query all positions."""
        if not self._connected:
            raise RuntimeError("QMT adapter not connected")
        return list(self._positions.values())

    def query_orders(self) -> list[OrderSnapshot]:
        """Query all orders."""
        if not self._connected:
            raise RuntimeError("QMT adapter not connected")
        return [
            OrderSnapshot(
                broker_order_id=o.broker_order_id,
                instrument_id=o.instrument_id,
                side=o.side,
                order_type=o.order_type,
                price=o.price,
                quantity=o.quantity,
                filled_quantity=o.filled_quantity,
                status=o.status,
                submit_time=o.submit_time,
            )
            for o in self._orders.values()
        ]

    def submit_order(
        self,
        instrument_id: str,
        side: str,
        order_type: str,
        price: Decimal,
        quantity: int,
    ) -> str:
        """Submit an order. Returns broker_order_id."""
        if not self._connected:
            raise RuntimeError("QMT adapter not connected")

        if self._fail_submit:
            raise RuntimeError("QMT mock: forced submit failure")

        broker_order_id = f"mock-{uuid.uuid4().hex[:12]}"

        # Simulate fill
        if self._partial_fill:
            filled_qty = quantity // 2
            filled_price = price
        else:
            filled_qty = quantity
            filled_price = price

        status = "filled" if filled_qty == quantity else "partial"

        order = _MockOrder(
            broker_order_id=broker_order_id,
            instrument_id=instrument_id,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            filled_quantity=filled_qty,
            filled_price=filled_price,
            status=status,
        )
        self._orders[broker_order_id] = order

        # Update positions
        if filled_qty > 0:
            self._update_position(instrument_id, side, filled_qty, filled_price)

        return broker_order_id

    def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order."""
        if not self._connected:
            raise RuntimeError("QMT adapter not connected")

        order = self._orders.get(broker_order_id)
        if order is None:
            return False

        if order.status in ("filled", "canceled", "rejected"):
            return False

        order.status = "canceled"
        return True

    def get_fill_status(self, broker_order_id: str) -> FillStatus:
        """Get fill status for an order."""
        if not self._connected:
            raise RuntimeError("QMT adapter not connected")

        order = self._orders.get(broker_order_id)
        if order is None:
            raise ValueError(f"Unknown order: {broker_order_id}")

        return FillStatus(
            broker_order_id=broker_order_id,
            filled_quantity=order.filled_quantity,
            filled_price=order.filled_price,
            status=order.status,
        )

    def _update_position(
        self,
        instrument_id: str,
        side: str,
        quantity: int,
        price: Decimal,
    ) -> None:
        """Update mock position and account cash after fill."""
        trade_value = price * Decimal(quantity)

        pos = self._positions.get(instrument_id)
        if pos is None:
            if side == "buy":
                self._positions[instrument_id] = PositionSnapshot(
                    instrument_id=instrument_id,
                    quantity=quantity,
                    available_quantity=0,  # T+1
                    cost_price=price,
                    market_price=price,
                    unrealized_pnl=Decimal("0"),
                )
                # Deduct cash
                self._account.available_cash -= trade_value
                self._account.frozen_cash += trade_value
                self._account.market_value += trade_value
                self._account.total_asset = self._account.available_cash + self._account.market_value
            return

        if side == "buy":
            # Update cost price as weighted average
            total_qty = pos.quantity + quantity
            new_cost = (pos.cost_price * pos.quantity + price * quantity) / total_qty
            pos.quantity = total_qty
            pos.cost_price = new_cost
            pos.market_price = price
            # Deduct cash
            self._account.available_cash -= trade_value
            self._account.frozen_cash += trade_value
            self._account.market_value += trade_value
            self._account.total_asset = self._account.available_cash + self._account.market_value
        elif side == "sell":
            # Add proceeds to cash
            self._account.available_cash += trade_value
            self._account.market_value -= pos.cost_price * Decimal(quantity)
            self._account.total_asset = self._account.available_cash + self._account.market_value
            pos.quantity = max(0, pos.quantity - quantity)
            if pos.quantity == 0:
                del self._positions[instrument_id]
