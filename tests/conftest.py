"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hqmts.db.base import Base
from hqmts.infra.config import Settings, load_settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    """Load Settings for the research environment."""
    return load_settings("research")


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """In-memory SQLite async session for integration tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()
