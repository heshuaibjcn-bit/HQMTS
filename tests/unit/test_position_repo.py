"""Tests for PositionRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.db.base import Base
from hqmts.db.models.position import PositionORM
from hqmts.db.repositories.position_repo import PositionRepository

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


class TestGetByAccountAndInstrument:
    @pytest.mark.asyncio
    async def test_returns_position(self, session):
        session.add(PositionORM(
            account_id="acc-1", instrument_id="600000.SH",
            total_quantity=100, cost_price=Decimal("10.5"), updated_at=_NOW,
        ))
        await session.flush()
        repo = PositionRepository(session)
        result = await repo.get_by_account_and_instrument("acc-1", "600000.SH")
        assert result is not None
        assert result.total_quantity == 100

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, session):
        repo = PositionRepository(session)
        result = await repo.get_by_account_and_instrument("acc-1", "600000.SH")
        assert result is None


class TestGetPositionsByAccount:
    @pytest.mark.asyncio
    async def test_returns_all_positions(self, session):
        session.add(PositionORM(account_id="acc-1", instrument_id="600000.SH", total_quantity=100, updated_at=_NOW))
        session.add(PositionORM(account_id="acc-1", instrument_id="000001.SZ", total_quantity=200, updated_at=_NOW))
        await session.flush()
        repo = PositionRepository(session)
        results = await repo.get_positions_by_account("acc-1")
        assert len(results) == 2


class TestGetOpenPositions:
    @pytest.mark.asyncio
    async def test_returns_only_open_positions(self, session):
        session.add(PositionORM(account_id="acc-1", instrument_id="600000.SH", total_quantity=100, updated_at=_NOW))
        session.add(PositionORM(account_id="acc-1", instrument_id="000001.SZ", total_quantity=0, updated_at=_NOW))
        await session.flush()
        repo = PositionRepository(session)
        results = await repo.get_open_positions("acc-1")
        assert len(results) == 1
        assert results[0].instrument_id == "600000.SH"
