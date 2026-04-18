"""Tests for AuditRepository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.db.base import Base
from hqmts.db.models.audit import AuditEventORM
from hqmts.db.repositories.audit_repo import AuditRepository

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


async def _seed(session, count=3, entity_id="ord-001", correlation_id="corr-001"):
    for i in range(count):
        session.add(AuditEventORM(
            audit_event_id=f"ae-{i:03d}",
            event_type="api_request",
            entity_type="order",
            entity_id=entity_id,
            environment="research",
            actor="user_test",
            action=f"POST /orders/{entity_id}",
            details_json='{"status_code": 200}',
            alert_level="P3",
            correlation_id=correlation_id,
            timestamp=_NOW - timedelta(minutes=count - i),
        ))
    await session.flush()


class TestGetByEntity:
    @pytest.mark.asyncio
    async def test_returns_events_for_entity(self, session):
        await _seed(session, count=3, entity_id="ord-001")
        repo = AuditRepository(session)
        results = await repo.get_by_entity("order", "ord-001")
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_entity(self, session):
        await _seed(session, count=1, entity_id="ord-001")
        repo = AuditRepository(session)
        results = await repo.get_by_entity("order", "ord-nonexistent")
        assert len(results) == 0


class TestGetByTimeRange:
    @pytest.mark.asyncio
    async def test_returns_events_in_range(self, session):
        await _seed(session, count=3)
        repo = AuditRepository(session)
        start = _NOW - timedelta(hours=1)
        end = _NOW + timedelta(hours=1)
        results = await repo.get_by_time_range(start, end)
        assert len(results) == 3


class TestGetByCorrelationId:
    @pytest.mark.asyncio
    async def test_returns_trace(self, session):
        await _seed(session, count=2, correlation_id="corr-001")
        repo = AuditRepository(session)
        results = await repo.get_by_correlation_id("corr-001")
        assert len(results) == 2


class TestImmutability:
    @pytest.mark.asyncio
    async def test_update_raises(self, session):
        repo = AuditRepository(session)
        event = AuditEventORM(
            audit_event_id="ae-imm", event_type="test", entity_type="order",
            entity_id="x", environment="test", actor="test", action="test",
            timestamp=_NOW,
        )
        session.add(event)
        await session.flush()
        with pytest.raises(NotImplementedError):
            await repo.update(event)

    @pytest.mark.asyncio
    async def test_delete_raises(self, session):
        repo = AuditRepository(session)
        event = AuditEventORM(
            audit_event_id="ae-imm2", event_type="test", entity_type="order",
            entity_id="x", environment="test", actor="test", action="test",
            timestamp=_NOW,
        )
        session.add(event)
        await session.flush()
        with pytest.raises(NotImplementedError):
            await repo.delete(event)
