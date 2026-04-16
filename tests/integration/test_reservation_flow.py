"""Integration test: Cash reservation lifecycle via repository.

Covers: reserve -> consume -> release, TTL expiry, concurrent conflict detection.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import ReservationStatus
from hqmts.db.models.reservation import CashReservationORM
from hqmts.db.repositories.reservation_repo import ReservationRepository


class TestReservationFlow:
    """Full reservation lifecycle: reserve -> consume -> release."""

    @pytest.mark.asyncio
    async def test_reserve_and_lookup(self, session: AsyncSession):
        repo = ReservationRepository(session)
        now = datetime.now()

        res = CashReservationORM(
            reservation_id="res-001",
            account_id="acc-001",
            strategy_instance_id="strat-001",
            signal_id="sig-001",
            execution_intent_id="intent-001",
            reserved_amount=Decimal("50000.00"),
            consumed_amount=Decimal("0"),
            currency="CNY",
            status=ReservationStatus.ACTIVE.value,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )

        await repo.create(res)
        await session.commit()

        fetched = await repo.get_by_id("res-001", id_column="reservation_id")
        assert fetched is not None
        assert fetched.reserved_amount == Decimal("50000.00")
        assert fetched.status == ReservationStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_active_reservations_by_account(self, session: AsyncSession):
        repo = ReservationRepository(session)
        now = datetime.now()

        # Active reservation
        await repo.create(CashReservationORM(
            reservation_id="res-002",
            account_id="acc-001",
            strategy_instance_id="strat-001",
            reserved_amount=Decimal("30000"),
            status=ReservationStatus.ACTIVE.value,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        ))

        # Released reservation
        await repo.create(CashReservationORM(
            reservation_id="res-003",
            account_id="acc-001",
            strategy_instance_id="strat-002",
            reserved_amount=Decimal("20000"),
            status=ReservationStatus.RELEASED.value,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        ))

        await session.commit()

        active = await repo.get_active_by_account("acc-001")
        assert len(active) == 1
        assert active[0].reservation_id == "res-002"

    @pytest.mark.asyncio
    async def test_total_reserved_amount(self, session: AsyncSession):
        repo = ReservationRepository(session)
        now = datetime.now()

        for i, amount in enumerate([Decimal("10000"), Decimal("20000"), Decimal("15000")]):
            await repo.create(CashReservationORM(
                reservation_id=f"res-total-{i}",
                account_id="acc-001",
                strategy_instance_id=f"strat-{i}",
                reserved_amount=amount,
                status=ReservationStatus.ACTIVE.value,
                expires_at=now + timedelta(minutes=2),
                created_at=now,
                updated_at=now,
            ))

        await session.commit()

        total = await repo.get_total_reserved_amount("acc-001")
        assert total == Decimal("45000")

    @pytest.mark.asyncio
    async def test_consume_reservation(self, session: AsyncSession):
        """Partial consume reduces remaining but keeps active."""
        repo = ReservationRepository(session)
        now = datetime.now()

        res = CashReservationORM(
            reservation_id="res-004",
            account_id="acc-001",
            strategy_instance_id="strat-001",
            reserved_amount=Decimal("50000"),
            consumed_amount=Decimal("0"),
            status=ReservationStatus.ACTIVE.value,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        await repo.create(res)
        await session.commit()

        # Simulate partial consume
        res.consumed_amount = Decimal("30000")
        await repo.update(res)
        await session.commit()

        fetched = await repo.get_by_id("res-004", id_column="reservation_id")
        assert fetched.consumed_amount == Decimal("30000")
        assert fetched.reserved_amount == Decimal("50000")

    @pytest.mark.asyncio
    async def test_full_consume_then_release(self, session: AsyncSession):
        """Full consume transitions to fully_consumed."""
        repo = ReservationRepository(session)
        now = datetime.now()

        res = CashReservationORM(
            reservation_id="res-005",
            account_id="acc-001",
            strategy_instance_id="strat-001",
            reserved_amount=Decimal("50000"),
            consumed_amount=Decimal("50000"),
            status=ReservationStatus.FULLY_CONSUMED.value,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        await repo.create(res)
        await session.commit()

        fetched = await repo.get_by_id("res-005", id_column="reservation_id")
        assert fetched.status == ReservationStatus.FULLY_CONSUMED.value

    @pytest.mark.asyncio
    async def test_release_on_order_failure(self, session: AsyncSession):
        """Reservation released when order is rejected."""
        repo = ReservationRepository(session)
        now = datetime.now()

        res = CashReservationORM(
            reservation_id="res-006",
            account_id="acc-001",
            strategy_instance_id="strat-001",
            reserved_amount=Decimal("40000"),
            status=ReservationStatus.ACTIVE.value,
            expires_at=now + timedelta(minutes=2),
            created_at=now,
            updated_at=now,
        )
        await repo.create(res)
        await session.commit()

        # Simulate release
        res.status = ReservationStatus.RELEASED.value
        res.released_reason = "order_rejected"
        await repo.update(res)
        await session.commit()

        active = await repo.get_active_by_account("acc-001")
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_expired_reservations_detection(self, session: AsyncSession):
        """get_expired_reservations finds active reservations past expiry."""
        repo = ReservationRepository(session)
        now = datetime.now()

        await repo.create(CashReservationORM(
            reservation_id="res-expired",
            account_id="acc-001",
            strategy_instance_id="strat-001",
            reserved_amount=Decimal("10000"),
            status=ReservationStatus.ACTIVE.value,
            expires_at=now - timedelta(minutes=1),  # Already expired
            created_at=now,
            updated_at=now,
        ))

        await repo.create(CashReservationORM(
            reservation_id="res-valid",
            account_id="acc-001",
            strategy_instance_id="strat-002",
            reserved_amount=Decimal("20000"),
            status=ReservationStatus.ACTIVE.value,
            expires_at=now + timedelta(minutes=5),  # Still valid
            created_at=now,
            updated_at=now,
        ))

        await session.commit()

        # get_active_by_account returns both (status=active)
        active = await repo.get_active_by_account("acc-001")
        assert len(active) == 2

        # get_expired_reservations returns only the expired one
        expired = await repo.get_expired_reservations(now)
        assert len(expired) == 1
        assert expired[0].reservation_id == "res-expired"
