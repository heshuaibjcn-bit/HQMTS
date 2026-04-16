"""CashReservation domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import ReservationStatus
from hqmts.core.types import AccountId, ReservationId, StrategyInstanceId


class CashReservation(BaseModel):
    """Cash reservation for multi-strategy shared account (SAD 7.4, 16).

    Prevents over-commitment of available funds when multiple strategies
    share the same account.

    Key rules:
    - New positions must complete reservation first
    - Reservations for the same account are serialized (account_id)
    - Reservation is local semantics, not broker-level freeze
    - Available = QMT_available_cash - sum(active reservations)
    """

    reservation_id: ReservationId
    account_id: AccountId
    strategy_instance_id: StrategyInstanceId
    signal_id: str | None = None
    execution_intent_id: str | None = None
    reserved_amount: Decimal = Field(ge=0)
    consumed_amount: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = "CNY"
    status: ReservationStatus = ReservationStatus.ACTIVE
    expires_at: datetime
    released_reason: str = ""
    created_at: datetime
    updated_at: datetime

    @property
    def remaining_amount(self) -> Decimal:
        """Amount still available in this reservation."""
        return self.reserved_amount - self.consumed_amount

    def is_active(self) -> bool:
        """Check if reservation is still active and usable."""
        return self.status == ReservationStatus.ACTIVE and not self.is_expired()

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if reservation has expired."""
        check_time = now or datetime.now()
        return check_time > self.expires_at

    def can_consume(self, amount: Decimal) -> bool:
        """Check if the reservation can consume the given amount."""
        if not self.is_active():
            return False
        return amount <= self.remaining_amount
