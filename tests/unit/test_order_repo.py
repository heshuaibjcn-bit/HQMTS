"""Tests for OrderRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.db.base import Base
from hqmts.db.models.order import OrderORM
from hqmts.db.repositories.order_repo import OrderRepository


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


class TestGetByBrokerOrderId:
    @pytest.mark.asyncio
    async def test_returns_order(self, session):
        session.add(OrderORM(
            order_id="ord-001", account_id="acc-1", instrument_id="600000.SH",
            side="buy", price=Decimal("10.5"), quantity=100, broker_order_id="brk-001",
        ))
        await session.flush()
        repo = OrderRepository(session)
        result = await repo.get_by_broker_order_id("brk-001")
        assert result is not None
        assert result.order_id == "ord-001"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, session):
        repo = OrderRepository(session)
        result = await repo.get_by_broker_order_id("nonexistent")
        assert result is None


class TestGetActiveOrdersByAccount:
    @pytest.mark.asyncio
    async def test_returns_only_active_orders(self, session):
        session.add(OrderORM(order_id="ord-001", account_id="acc-1", instrument_id="600000.SH", side="buy", price=Decimal("10"), quantity=100, status="created"))
        session.add(OrderORM(order_id="ord-002", account_id="acc-1", instrument_id="000001.SZ", side="sell", price=Decimal("20"), quantity=200, status="filled"))
        await session.flush()
        repo = OrderRepository(session)
        results = await repo.get_active_orders_by_account("acc-1")
        assert len(results) == 1
        assert results[0].order_id == "ord-001"


class TestGetByInstrument:
    @pytest.mark.asyncio
    async def test_returns_orders_for_instrument(self, session):
        session.add(OrderORM(order_id="ord-001", account_id="acc-1", instrument_id="600000.SH", side="buy", price=Decimal("10"), quantity=100))
        session.add(OrderORM(order_id="ord-002", account_id="acc-1", instrument_id="000001.SZ", side="sell", price=Decimal("20"), quantity=200))
        await session.flush()
        repo = OrderRepository(session)
        results = await repo.get_by_instrument("600000.SH")
        assert len(results) == 1


class TestHasConflictingInflightOrders:
    @pytest.mark.asyncio
    async def test_detects_conflict(self, session):
        session.add(OrderORM(order_id="ord-001", account_id="acc-1", instrument_id="600000.SH", side="buy", price=Decimal("10"), quantity=100, status="created"))
        await session.flush()
        repo = OrderRepository(session)
        assert await repo.has_conflicting_inflight_orders("acc-1", "600000.SH", "buy") is True

    @pytest.mark.asyncio
    async def test_no_conflict_for_different_side(self, session):
        session.add(OrderORM(order_id="ord-001", account_id="acc-1", instrument_id="600000.SH", side="buy", price=Decimal("10"), quantity=100, status="created"))
        await session.flush()
        repo = OrderRepository(session)
        assert await repo.has_conflicting_inflight_orders("acc-1", "600000.SH", "sell") is False
