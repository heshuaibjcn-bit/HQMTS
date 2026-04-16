"""Common FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.connection import async_sessionmaker


def get_db_session_factory() -> async_sessionmaker[AsyncSession]:
    """Placeholder — in production, this would use the app's session factory."""
    from hqmts.infra.config import load_settings
    from hqmts.db.connection import create_engine, create_session_factory

    settings = load_settings()
    engine = create_engine(settings.database)
    return create_session_factory(engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for request handling."""
    factory = get_db_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
