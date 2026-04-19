"""Tests for BaseRepository generic CRUD operations."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from hqmts.db.base import Base
from hqmts.db.repositories.base import BaseRepository


class SampleORM(Base):
    """Minimal ORM for base repo tests."""
    __tablename__ = "_test_samples"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active")


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


@pytest_asyncio.fixture
def repo(session: AsyncSession) -> BaseRepository[SampleORM]:
    return BaseRepository(SampleORM, session)


class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_entity_when_found(self, repo, session):
        session.add(SampleORM(id="s1", name="Alpha"))
        await session.flush()
        result = await repo.get_by_id("s1")
        assert result is not None
        assert result.name == "Alpha"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, repo):
        result = await repo.get_by_id("nonexistent")
        assert result is None


class TestGetByField:
    @pytest.mark.asyncio
    async def test_returns_entity_by_name(self, repo, session):
        session.add(SampleORM(id="s1", name="Alpha"))
        await session.flush()
        result = await repo.get_by_field("name", "Alpha")
        assert result is not None
        assert result.id == "s1"


class TestGetMany:
    @pytest.mark.asyncio
    async def test_returns_all_without_filter(self, repo, session):
        for i in range(5):
            session.add(SampleORM(id=f"s{i}", name=f"Item {i}"))
        await session.flush()
        results = await repo.get_many()
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_filters_by_field(self, repo, session):
        session.add(SampleORM(id="s1", name="A", status="active"))
        session.add(SampleORM(id="s2", name="B", status="archived"))
        await session.flush()
        results = await repo.get_many(filters={"status": "active"})
        assert len(results) == 1
        assert results[0].name == "A"

    @pytest.mark.asyncio
    async def test_respects_limit(self, repo, session):
        for i in range(10):
            session.add(SampleORM(id=f"s{i}", name=f"Item {i}"))
        await session.flush()
        results = await repo.get_many(limit=3)
        assert len(results) == 3


class TestCount:
    @pytest.mark.asyncio
    async def test_counts_all(self, repo, session):
        session.add(SampleORM(id="s1", name="A"))
        session.add(SampleORM(id="s2", name="B"))
        await session.flush()
        assert await repo.count() == 2

    @pytest.mark.asyncio
    async def test_counts_with_filter(self, repo, session):
        session.add(SampleORM(id="s1", name="A", status="active"))
        session.add(SampleORM(id="s2", name="B", status="archived"))
        await session.flush()
        assert await repo.count(filters={"status": "active"}) == 1


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_entity(self, repo, session):
        entity = SampleORM(id="s1", name="New")
        result = await repo.create(entity)
        assert result.name == "New"
        # Verify persisted
        found = await repo.get_by_id("s1")
        assert found is not None


class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_entity(self, repo, session):
        entity = SampleORM(id="s1", name="ToDelete")
        session.add(entity)
        await session.flush()
        await repo.delete(entity)
        found = await repo.get_by_id("s1")
        assert found is None
