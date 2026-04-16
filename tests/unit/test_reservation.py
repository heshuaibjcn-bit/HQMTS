"""Tests for Cash Reservation Manager."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from hqmts.core.enums import ReservationStatus
from hqmts.core.exceptions import InsufficientFundsError
from hqmts.domain.reservation import CashReservation


class TestCashReservation:
    def test_remaining_amount(self):
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            consumed_amount=Decimal("3000"),
            status=ReservationStatus.ACTIVE,
            expires_at=datetime.now() + timedelta(minutes=2),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert r.remaining_amount == Decimal("7000")

    def test_is_active(self):
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.ACTIVE,
            expires_at=datetime.now() + timedelta(minutes=2),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert r.is_active()

    def test_is_not_active_when_expired(self):
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.ACTIVE,
            expires_at=datetime.now() - timedelta(minutes=1),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert not r.is_active()

    def test_is_not_active_when_released(self):
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.RELEASED,
            expires_at=datetime.now() + timedelta(minutes=2),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert not r.is_active()

    def test_can_consume(self):
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            consumed_amount=Decimal("3000"),
            status=ReservationStatus.ACTIVE,
            expires_at=datetime.now() + timedelta(minutes=2),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert r.can_consume(Decimal("5000"))
        assert not r.can_consume(Decimal("8000"))

    def test_cannot_consume_when_not_active(self):
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.RELEASED,
            expires_at=datetime.now() + timedelta(minutes=2),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert not r.can_consume(Decimal("100"))
