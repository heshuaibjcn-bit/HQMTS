"""Common FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session from the app-level factory."""
    factory = request.app.state.db_session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
