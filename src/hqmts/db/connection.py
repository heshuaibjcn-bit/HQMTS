"""Database connection management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hqmts.infra.config import DatabaseConfig


def create_engine(config: DatabaseConfig):
    """Create async SQLAlchemy engine."""
    return create_async_engine(
        config.url,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        echo=config.echo,
    )


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
