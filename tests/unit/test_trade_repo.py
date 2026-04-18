"""Tests for TradeRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.db.base import Base
from hqmts.db.models.trade import TradeORM
from hqmts.db.repositories.trade_repo import TradeRepository

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


class TestGetByBrokerTradeId:
    @pytest.mark.asyncio
    async def test_returns_trade(self, session):
        session.add(TradeORM(
            trade_id="trd-001", order_id="ord-001", instrument_id="600000.SH",
            traded_at=_NOW, trade_price=Decimal("10.5"), trade_quantity=100,
            broker_trade_id="btrd-001",
        ))
        await session.flush()
        repo = TradeRepository(session)
        result = await repo.get_by_broker_trade_id("btrd-001")
        assert result is not None
        assert result.trade_id == "trd-001"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, session):
        repo = TradeRepository(session)
        result = await repo.get_by_broker_trade_id("nonexistent")
        assert result is None


class TestGetTradesByOrder:
    @pytest.mark.asyncio
    async def test_returns_trades_for_order(self, session):
        session.add(TradeORM(trade_id="trd-001", order_id="ord-001", instrument_id="600000.SH", traded_at=_NOW, trade_price=Decimal("10"), trade_quantity=50))
        session.add(TradeORM(trade_id="trd-002", order_id="ord-001", instrument_id="600000.SH", traded_at=_NOW, trade_price=Decimal("10.5"), trade_quantity=50))
        session.add(TradeORM(trade_id="trd-003", order_id="ord-002", instrument_id="000001.SZ", traded_at=_NOW, trade_price=Decimal("20"), trade_quantity=100))
        await session.flush()
        repo = TradeRepository(session)
        results = await repo.get_trades_by_order("ord-001")
        assert len(results) == 2


class TestGetTradesByInstrument:
    @pytest.mark.asyncio
    async def test_returns_trades_for_instrument(self, session):
        session.add(TradeORM(trade_id="trd-001", order_id="ord-001", instrument_id="600000.SH", traded_at=_NOW, trade_price=Decimal("10"), trade_quantity=100))
        session.add(TradeORM(trade_id="trd-002", order_id="ord-002", instrument_id="000001.SZ", traded_at=_NOW, trade_price=Decimal("20"), trade_quantity=200))
        await session.flush()
        repo = TradeRepository(session)
        results = await repo.get_trades_by_instrument("600000.SH")
        assert len(results) == 1
