"""Redis client wrapper."""

from __future__ import annotations

import redis.asyncio as aioredis

from hqmts.infra.config import RedisConfig


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self, config: RedisConfig) -> None:
        self._config = config
        self._pool: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._pool = aioredis.from_url(
            self._config.url,
            max_connections=self._config.pool_size,
            decode_responses=True,
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    @property
    def client(self) -> aioredis.Redis:
        if self._pool is None:
            msg = "Redis not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._pool
