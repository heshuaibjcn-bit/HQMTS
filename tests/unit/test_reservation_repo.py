"""Tests for ReservationRepository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.db.base import Base
from hqmts.db.models.reservation import CashReservationORM
from hqmts.db.repositories.reservation_repo import ReservationRepository

_NOW = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


class TestGetActiveByAccount:
    @pytest.mark.asyncio
    async def test_returns_active_reservations(self, session):
        session.add(CashReservationORM(
            reservation_id="res-001", account_id="acc-1", strategy_instance_id="si-1",
            reserved_amount=Decimal("5000"), expires_at=_NOW + timedelta(hours=1), status="active",
        ))
        session.add(CashReservationORM(
            reservation_id="res-002", account_id="acc-1", strategy_instance_id="si-1",
            reserved_amount=Decimal("3000"), expires_at=_NOW + timedelta(hours=1), status="released",
        ))
        await session.flush()
        repo = ReservationRepository(session)
        results = await repo.get_active_by_account("acc-1")
        assert len(results) == 1
        assert results[0].reservation_id == "res-001"


class TestGetTotalReservedAmount:
    @pytest.mark.asyncio
    async def test_sums_active_reservations(self, session):
        session.add(CashReservationORM(
            reservation_id="res-001", account_id="acc-1", strategy_instance_id="si-1",
            reserved_amount=Decimal("5000"), expires_at=_NOW + timedelta(hours=1), status="active",
        ))
        session.add(CashReservationORM(
            reservation_id="res-002", account_id="acc-1", strategy_instance_id="si-1",
            reserved_amount=Decimal("3000"), expires_at=_NOW + timedelta(hours=1), status="active",
        ))
        await session.flush()
        repo = ReservationRepository(session)
        total = await repo.get_total_reserved_amount("acc-1")
        assert total == Decimal("8000")


class TestGetExpiredReservations:
    @pytest.mark.asyncio
    async def test_finds_expired(self, session):
        session.add(CashReservationORM(
            reservation_id="res-001", account_id="acc-1", strategy_instance_id="si-1",
            reserved_amount=Decimal("5000"), expires_at=_NOW - timedelta(hours=1), status="active",
        ))
        session.add(CashReservationORM(
            reservation_id="res-002", account_id="acc-1", strategy_instance_id="si-1",
            reserved_amount=Decimal("3000"), expires_at=_NOW + timedelta(hours=1), status="active",
        ))
        await session.flush()
        repo = ReservationRepository(session)
        expired = await repo.get_expired_reservations(_NOW)
        assert len(expired) == 1
        assert expired[0].reservation_id == "res-001"


class TestGetByExecutionIntent:
    @pytest.mark.asyncio
    async def test_finds_reservation(self, session):
        session.add(CashReservationORM(
            reservation_id="res-001", account_id="acc-1", strategy_instance_id="si-1",
            reserved_amount=Decimal("5000"), expires_at=_NOW + timedelta(hours=1),
            execution_intent_id="ei-001",
        ))
        await session.flush()
        repo = ReservationRepository(session)
        result = await repo.get_by_execution_intent("ei-001")
        assert result is not None
        assert result.reservation_id == "res-001"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, session):
        repo = ReservationRepository(session)
        result = await repo.get_by_execution_intent("nonexistent")
        assert result is None
