"""Database initialization script."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hqmts.db.base import Base
from hqmts.infra.config import load_settings


async def init_db() -> None:
    settings = load_settings()
    engine = create_async_engine(settings.database.url, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Database schema created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
