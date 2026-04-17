"""Tests for Cash Reservation Manager."""

import pytest
from datetime import timedelta
from decimal import Decimal

from hqmts.core.enums import ReservationStatus
from hqmts.core.exceptions import InsufficientFundsError
from hqmts.core.types import now_shanghai
from hqmts.domain.reservation import CashReservation


class TestCashReservation:
    def test_remaining_amount(self):
        now = now_shanghai()
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            consumed_amount=Decimal("3000"),
            status=ReservationStatus.ACTIVE,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        assert r.remaining_amount == Decimal("7000")

    def test_is_active(self):
        now = now_shanghai()
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.ACTIVE,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        assert r.is_active()

    def test_is_not_active_when_expired(self):
        now = now_shanghai()
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.ACTIVE,
            expires_at=now - timedelta(minutes=1),
            created_at=now,
            updated_at=now,
        )
        assert not r.is_active()

    def test_is_not_active_when_released(self):
        now = now_shanghai()
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.RELEASED,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        assert not r.is_active()

    def test_can_consume(self):
        now = now_shanghai()
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            consumed_amount=Decimal("3000"),
            status=ReservationStatus.ACTIVE,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        assert r.can_consume(Decimal("5000"))
        assert not r.can_consume(Decimal("8000"))

    def test_cannot_consume_when_not_active(self):
        now = now_shanghai()
        r = CashReservation(
            reservation_id="r1",
            account_id="acc1",
            strategy_instance_id="strat1",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.RELEASED,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        assert not r.can_consume(Decimal("100"))


class TestReservationManagerSafety:
    """Tests for ReservationManager available_cash enforcement."""

    @pytest.mark.asyncio
    async def test_reserve_raises_when_available_cash_none(self):
        from unittest.mock import AsyncMock

        from hqmts.reservation.manager import ReservationManager

        repo = AsyncMock()
        manager = ReservationManager(reservation_repo=repo)
        with pytest.raises(ValueError, match="available_cash must be provided"):
            await manager.reserve(
                account_id="acc-001",
                strategy_instance_id="strat-001",
                amount=Decimal("10000"),
                available_cash=None,
            )

    @pytest.mark.asyncio
    async def test_reserve_raises_insufficient_funds(self):
        from unittest.mock import AsyncMock

        from hqmts.reservation.manager import ReservationManager

        repo = AsyncMock()
        repo.get_total_reserved_amount = AsyncMock(return_value=Decimal("90000"))
        manager = ReservationManager(reservation_repo=repo)
        with pytest.raises(InsufficientFundsError):
            await manager.reserve(
                account_id="acc-001",
                strategy_instance_id="strat-001",
                amount=Decimal("20000"),
                available_cash=Decimal("100000"),
            )
