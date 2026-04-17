"""Paper trading mode (FR-BT-005).

Simulates real-time execution without actual orders. Runs the full
signal → risk → execution pipeline, records decisions, but submits
to a mock broker instead of real QMT.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from hqmts.core.enums import Cycle, RiskResultType, Side, SignalType
from hqmts.core.types import now_shanghai
from hqmts.domain.bar import Bar
from hqmts.domain.signal import Signal

if TYPE_CHECKING:
    from hqmts.risk.engine import RiskContext, RiskEngine
    from hqmts.reservation.manager import ReservationManager

logger = logging.getLogger(__name__)


class PaperOrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass
class PaperOrder:
    """A paper trading order with simulated fill."""

    order_id: str
    signal_id: str
    instrument_id: str
    side: str
    order_type: str
    price: Decimal
    quantity: int
    status: PaperOrderStatus = PaperOrderStatus.PENDING
    fill_price: Decimal = Decimal("0")
    fill_quantity: int = 0
    commission: Decimal = Decimal("0")
    stamp_tax: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=now_shanghai)
    filled_at: datetime | None = None
    reject_reason: str = ""


@dataclass
class PaperPosition:
    """Paper trading position."""

    instrument_id: str
    quantity: int = 0
    available_quantity: int = 0  # T+1
    cost_price: Decimal = Decimal("0")
    today_bought: int = 0


@dataclass
class PaperTradingState:
    """Complete state of the paper trading session."""

    session_id: str
    strategy_name: str
    started_at: datetime
    initial_cash: Decimal
    cash: Decimal = Decimal("0")
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    orders: list[PaperOrder] = field(default_factory=list)
    daily_snapshots: list[dict] = field(default_factory=list)
    is_active: bool = True


class PaperTradingEngine:
    """Paper trading engine that simulates execution without real orders.

    Runs the same strategy logic as backtest but in real-time fashion:
    - Receives bars one at a time (as they arrive)
    - Generates signals through strategy
    - Creates paper orders instead of real orders
    - Tracks positions and P&L
    """

    def __init__(
        self,
        session_id: str,
        strategy_name: str,
        initial_cash: Decimal = Decimal("1000000"),
        commission_rate: Decimal = Decimal("0.0003"),
        commission_min: Decimal = Decimal("5"),
        stamp_tax_rate: Decimal = Decimal("0.001"),
        lot_size: int = 100,
        risk_engine: RiskEngine | None = None,
        reservation_manager: ReservationManager | None = None,
        account_id: str | None = None,
    ) -> None:
        self._state = PaperTradingState(
            session_id=session_id,
            strategy_name=strategy_name,
            started_at=now_shanghai(),
            initial_cash=initial_cash,
            cash=initial_cash,
        )
        self._commission_rate = commission_rate
        self._commission_min = commission_min
        self._stamp_tax_rate = stamp_tax_rate
        self._lot_size = lot_size
        self._risk_engine = risk_engine
        self._reservation_manager = reservation_manager
        self._account_id = account_id
        self._active_reservations: dict[str, str] = {}  # order_id -> reservation_id

    @property
    def state(self) -> PaperTradingState:
        return self._state

    async def submit_signal(
        self,
        signal: Signal,
        reference_price: Decimal,
        risk_context: RiskContext | None = None,
    ) -> PaperOrder:
        """Convert a signal into a paper order.

        Calculates quantity based on available cash (buy) or position (sell).
        """
        instrument_id = str(signal.instrument_id)

        buy_types = {SignalType.OPEN_LONG, SignalType.CLOSE_SHORT}
        sell_types = {SignalType.CLOSE_LONG, SignalType.OPEN_SHORT}

        if signal.signal_type in buy_types:
            side = "buy"
        elif signal.signal_type in sell_types:
            side = "sell"
        elif signal.signal_type == SignalType.FLATTEN:
            side = "sell"
        else:
            # HOLD or unknown — no action
            return PaperOrder(
                order_id=str(uuid.uuid4()),
                signal_id=str(signal.signal_id),
                instrument_id=instrument_id,
                side="none",
                order_type="market",
                price=reference_price,
                quantity=0,
                status=PaperOrderStatus.REJECTED,
                reject_reason="Signal type does not produce an order",
            )
        quantity = 0

        if side == "buy":
            # Calculate max affordable quantity, reserving buffer for commission
            if reference_price > 0:
                effective_cash = self._state.cash / (Decimal("1") + self._commission_rate)
                max_qty = int(effective_cash / (reference_price * self._lot_size)) * self._lot_size
                quantity = max_qty
        else:
            # Sell available quantity
            pos = self._state.positions.get(instrument_id)
            if pos:
                quantity = pos.available_quantity
            else:
                quantity = 0

        if quantity <= 0:
            return PaperOrder(
                order_id=str(uuid.uuid4()),
                signal_id=str(signal.signal_id),
                instrument_id=instrument_id,
                side=side,
                order_type="market",
                price=reference_price,
                quantity=0,
                status=PaperOrderStatus.REJECTED,
                reject_reason="Insufficient cash or position",
            )

        # Pre-trade risk check (if risk engine provided)
        if self._risk_engine is not None and risk_context is not None:
            risk_result = await self._risk_engine.evaluate(risk_context)
            if risk_result.result_type == RiskResultType.REJECT:
                logger.info(
                    "PAPER_RISK_REJECT signal=%s reason=%s",
                    signal.signal_id, risk_result.reject_reason,
                )
                return PaperOrder(
                    order_id=str(uuid.uuid4()),
                    signal_id=str(signal.signal_id),
                    instrument_id=instrument_id,
                    side=side,
                    order_type="market",
                    price=reference_price,
                    quantity=0,
                    status=PaperOrderStatus.REJECTED,
                    reject_reason=f"Risk rejected: {risk_result.reject_reason}",
                )
            if risk_result.result_type == RiskResultType.DELAY:
                return PaperOrder(
                    order_id=str(uuid.uuid4()),
                    signal_id=str(signal.signal_id),
                    instrument_id=instrument_id,
                    side=side,
                    order_type="market",
                    price=reference_price,
                    quantity=0,
                    status=PaperOrderStatus.REJECTED,
                    reject_reason="Risk delayed",
                )
            # Resize: adjust quantity
            if (
                risk_result.result_type == RiskResultType.RESIZE
                and risk_result.resized_quantity is not None
            ):
                quantity = min(quantity, risk_result.resized_quantity)

        # Cash reservation for opening positions (if reservation manager provided)
        reservation_id: str | None = None
        opening_types = {SignalType.OPEN_LONG, SignalType.OPEN_SHORT}
        if (
            self._reservation_manager is not None
            and signal.signal_type in opening_types
            and reference_price > 0
            and self._account_id is not None
        ):
            try:
                reservation = await self._reservation_manager.reserve(
                    account_id=self._account_id,  # type: ignore
                    strategy_instance_id=signal.strategy_instance_id,
                    amount=reference_price * quantity,
                    signal_id=signal.signal_id,
                    available_cash=self._state.cash,
                )
                reservation_id = reservation.reservation_id
            except Exception as exc:
                logger.warning("PAPER_RESERVE_FAILED signal=%s error=%s", signal.signal_id, exc)
                return PaperOrder(
                    order_id=str(uuid.uuid4()),
                    signal_id=str(signal.signal_id),
                    instrument_id=instrument_id,
                    side=side,
                    order_type="market",
                    price=reference_price,
                    quantity=0,
                    status=PaperOrderStatus.REJECTED,
                    reject_reason=f"Reservation failed: {exc}",
                )

        order = PaperOrder(
            order_id=str(uuid.uuid4()),
            signal_id=str(signal.signal_id),
            instrument_id=instrument_id,
            side=side,
            order_type="market",
            price=reference_price,
            quantity=quantity,
        )
        self._state.orders.append(order)
        if reservation_id is not None:
            self._active_reservations[order.order_id] = reservation_id
        return order

    async def fill_order(self, order: PaperOrder, fill_price: Decimal) -> PaperOrder:
        """Simulate order fill at the given price."""
        if order.status != PaperOrderStatus.PENDING:
            return order

        commission = max(
            fill_price * Decimal(order.quantity) * self._commission_rate,
            self._commission_min,
        )
        stamp_tax = Decimal("0")
        if order.side == "sell":
            stamp_tax = fill_price * Decimal(order.quantity) * self._stamp_tax_rate

        total_cost = fill_price * Decimal(order.quantity) + commission + stamp_tax

        if order.side == "buy":
            if total_cost > self._state.cash:
                order.status = PaperOrderStatus.REJECTED
                order.reject_reason = "Insufficient cash"
                await self._release_reservation(order.order_id, "Insufficient cash on fill")
                return order
            self._state.cash -= total_cost
            self._update_position_buy(order.instrument_id, order.quantity, fill_price)
        else:
            self._state.cash += fill_price * Decimal(order.quantity) - commission - stamp_tax
            self._update_position_sell(order.instrument_id, order.quantity)

        order.status = PaperOrderStatus.FILLED
        order.fill_price = fill_price
        order.fill_quantity = order.quantity
        order.commission = commission
        order.stamp_tax = stamp_tax
        order.filled_at = now_shanghai()

        # Consume reservation on fill
        await self._consume_reservation(order.order_id, fill_price * Decimal(order.quantity))

        return order

    def end_of_day_reset(self) -> None:
        """Reset T+1 state at end of trading day."""
        for pos in self._state.positions.values():
            pos.available_quantity = pos.quantity
            pos.today_bought = 0

        # Snapshot
        total_asset = self._state.cash
        for pos in self._state.positions.values():
            total_asset += pos.cost_price * Decimal(pos.quantity)

        self._state.daily_snapshots.append({
            "date": now_shanghai().strftime("%Y%m%d"),
            "cash": str(self._state.cash),
            "total_asset": str(total_asset),
            "positions": {k: {"qty": v.quantity, "cost": str(v.cost_price)} for k, v in self._state.positions.items()},
        })

    def get_total_asset(self, prices: dict[str, Decimal] | None = None) -> Decimal:
        """Calculate total account value."""
        total = self._state.cash
        for iid, pos in self._state.positions.items():
            if prices and iid in prices:
                total += prices[iid] * Decimal(pos.quantity)
            else:
                total += pos.cost_price * Decimal(pos.quantity)
        return total

    def stop(self) -> None:
        """Stop the paper trading session."""
        self._state.is_active = False

    def _update_position_buy(self, instrument_id: str, quantity: int, price: Decimal) -> None:
        pos = self._state.positions.get(instrument_id)
        if pos is None:
            self._state.positions[instrument_id] = PaperPosition(
                instrument_id=instrument_id,
                quantity=quantity,
                available_quantity=0,  # T+1
                cost_price=price,
                today_bought=quantity,
            )
        else:
            total_qty = pos.quantity + quantity
            new_cost = (pos.cost_price * Decimal(pos.quantity) + price * Decimal(quantity)) / Decimal(total_qty)
            pos.quantity = total_qty
            pos.cost_price = new_cost
            pos.today_bought += quantity

    def _update_position_sell(self, instrument_id: str, quantity: int) -> None:
        pos = self._state.positions.get(instrument_id)
        if pos:
            pos.quantity = max(0, pos.quantity - quantity)
            pos.available_quantity = max(0, pos.available_quantity - quantity)
            if pos.quantity == 0:
                del self._state.positions[instrument_id]

    async def _consume_reservation(self, order_id: str, fill_amount: Decimal) -> None:
        """Consume reservation on successful fill."""
        reservation_id = self._active_reservations.pop(order_id, None)
        if reservation_id and self._reservation_manager:
            try:
                await self._reservation_manager.consume(reservation_id, fill_amount)
            except Exception as exc:
                logger.warning(
                    "PAPER_CONSUME_FAILED order=%s reservation=%s error=%s",
                    order_id, reservation_id, exc,
                )

    async def _release_reservation(self, order_id: str, reason: str) -> None:
        """Release reservation on order rejection/failure."""
        reservation_id = self._active_reservations.pop(order_id, None)
        if reservation_id and self._reservation_manager:
            try:
                await self._reservation_manager.release(reservation_id, reason=reason)
            except Exception as exc:
                logger.warning(
                    "PAPER_RELEASE_FAILED order=%s reservation=%s error=%s",
                    order_id, reservation_id, exc,
                )
