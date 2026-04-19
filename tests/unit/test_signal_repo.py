"""Tests for SignalRepository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.db.base import Base
from hqmts.db.models.signal import SignalORM
from hqmts.db.repositories.signal_repo import SignalRepository

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


async def _seed(session, count=3, strategy_instance_id="si-alpha"):
    for i in range(count):
        session.add(SignalORM(
            signal_id=f"sig-{i:03d}",
            strategy_instance_id=strategy_instance_id,
            strategy_version="1.0.0",
            decision_time=_NOW - timedelta(hours=count - i),
            instrument_id=f"inst-{i}",
            signal_type="entry",
            target_direction="long",
            valid_until=_NOW + timedelta(hours=1),
        ))
    await session.flush()


class TestGetByStrategyInstance:
    @pytest.mark.asyncio
    async def test_returns_signals_for_instance(self, session):
        await _seed(session, count=3, strategy_instance_id="si-alpha")
        repo = SignalRepository(session)
        results = await repo.get_by_strategy_instance("si-alpha")
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_instance(self, session):
        await _seed(session, count=1, strategy_instance_id="si-alpha")
        repo = SignalRepository(session)
        results = await repo.get_by_strategy_instance("si-unknown")
        assert len(results) == 0


class TestGetByTimeRange:
    @pytest.mark.asyncio
    async def test_returns_signals_in_range(self, session):
        await _seed(session, count=3, strategy_instance_id="si-alpha")
        repo = SignalRepository(session)
        start = _NOW - timedelta(hours=4)
        end = _NOW + timedelta(hours=1)
        results = await repo.get_by_time_range("si-alpha", start, end)
        assert len(results) == 3


class TestGetByInstrument:
    @pytest.mark.asyncio
    async def test_returns_signals_for_instrument(self, session):
        await _seed(session, count=2, strategy_instance_id="si-alpha")
        repo = SignalRepository(session)
        results = await repo.get_by_instrument("inst-0")
        assert len(results) == 1
        assert results[0].instrument_id == "inst-0"
