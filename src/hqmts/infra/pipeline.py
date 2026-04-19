"""Async pipeline bus for inter-service communication.

Two implementations:
- RedisStreamBus: Production, uses Redis Streams (XADD/XREADGROUP/XACK).
- InProcessBus: Fallback for testing, uses asyncio.Queue.

Both implement the same PipelineBus protocol so services can switch
between them without code changes.
"""

from __future__ import annotations

import abc
import asyncio
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine

from hqmts.core.types import now_shanghai

logger = logging.getLogger(__name__)

# Stream names
STREAM_SIGNALS = "hqmts:signals"
STREAM_RISK_RESULTS = "hqmts:risk_results"
STREAM_INTENTS = "hqmts:intents"
STREAM_ORDERS = "hqmts:orders"
STREAM_POSITIONS = "hqmts:positions"
STREAM_ALERTS = "hqmts:alerts"
STREAM_AGENT_TASKS = "hqmts:agent_tasks"

ALL_STREAMS = [
    STREAM_SIGNALS,
    STREAM_RISK_RESULTS,
    STREAM_INTENTS,
    STREAM_ORDERS,
    STREAM_POSITIONS,
    STREAM_ALERTS,
    STREAM_AGENT_TASKS,
]


@dataclass
class PipelineMessage:
    """A message on the pipeline bus."""

    stream: str
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: now_shanghai().isoformat(),
    )


# Type for consumer callbacks
ConsumerCallback = Callable[[PipelineMessage], Coroutine[Any, Any, None]]


class PipelineBus(abc.ABC):
    """Abstract async message bus for the trading pipeline."""

    @abc.abstractmethod
    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        """Publish a message to a stream. Returns the message ID."""

    @abc.abstractmethod
    async def subscribe(
        self,
        stream: str,
        group: str,
        callback: ConsumerCallback,
    ) -> None:
        """Subscribe to a stream with a consumer group."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Start all consumers."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Gracefully stop all consumers."""


# ---------------------------------------------------------------------------
# In-process implementation (for testing / no-Redis environments)
# ---------------------------------------------------------------------------


class InProcessBus(PipelineBus):
    """In-process async message bus using asyncio.Queue.

    Each subscriber gets its own queue (fan-out / pub-sub semantics).
    No external dependencies. Suitable for unit tests and single-process
    deployments where Redis is not available.
    """

    def __init__(self) -> None:
        self._subscriber_queues: list[tuple[str, str, asyncio.Queue[PipelineMessage], ConsumerCallback]] = []
        self._consumers: list[asyncio.Task[None]] = []
        self._running = False

    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        msg = PipelineMessage(stream=stream, payload=payload)
        # Fan-out: deliver to every subscriber on this stream
        for s_stream, _, queue, _ in self._subscriber_queues:
            if s_stream == stream:
                await queue.put(msg)
        return msg.message_id

    async def subscribe(
        self,
        stream: str,
        group: str,
        callback: ConsumerCallback,
    ) -> None:
        queue: asyncio.Queue[PipelineMessage] = asyncio.Queue()
        self._subscriber_queues.append((stream, group, queue, callback))

        async def _consume() -> None:
            while self._running:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    await callback(msg)
                except Exception:
                    logger.exception(
                        "Consumer %s/%s error processing %s",
                        stream,
                        group,
                        msg.message_id,
                    )

        self._consumers.append(asyncio.create_task(_consume()))

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
        for task in self._consumers:
            task.cancel()
        for task in self._consumers:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consumers.clear()


# ---------------------------------------------------------------------------
# Redis Streams implementation (production)
# ---------------------------------------------------------------------------


class RedisStreamBus(PipelineBus):
    """Redis Streams-based message bus.

    Features:
    - Consumer groups for at-least-once delivery
    - XACK after successful processing
    - Graceful shutdown via cancellation

    Requires: redis>=5.0 (with asyncio support)
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._consumers: list[asyncio.Task[None]] = []
        self._running = False
        self._callbacks: dict[str, list[tuple[str, ConsumerCallback]]] = defaultdict(list)

    async def _ensure_redis(self) -> Any:
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        r = await self._ensure_redis()
        msg_id = await r.xadd(stream, payload)
        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)

    async def subscribe(
        self,
        stream: str,
        group: str,
        callback: ConsumerCallback,
    ) -> None:
        self._callbacks[stream].append((group, callback))

    async def start(self) -> None:
        r = await self._ensure_redis()
        self._running = True

        for stream, subscribers in self._callbacks.items():
            # Create consumer group (ignore if exists)
            try:
                await r.xgroup_create(stream, subscribers[0][0], id="0", mkstream=True)
            except Exception:
                pass  # Group may already exist

            for group, callback in subscribers:
                consumer_name = f"{group}-worker-{uuid.uuid4().hex[:8]}"
                task = asyncio.create_task(
                    self._consume_stream(r, stream, group, consumer_name, callback)
                )
                self._consumers.append(task)

    async def _consume_stream(
        self,
        r: Any,
        stream: str,
        group: str,
        consumer: str,
        callback: ConsumerCallback,
    ) -> None:
        while self._running:
            try:
                results = await r.xreadgroup(
                    group, consumer, {stream: ">"}, count=10, block=1000
                )
            except Exception:
                if not self._running:
                    break
                logger.exception("Redis XREADGROUP error on %s/%s", stream, group)
                await asyncio.sleep(1)
                continue

            if not results:
                continue

            for _, messages in results:
                for msg_id, fields in messages:
                    mid = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                    payload = {
                        k.decode() if isinstance(k, bytes) else k: (
                            v.decode() if isinstance(v, bytes) else v
                        )
                        for k, v in fields.items()
                    }
                    msg = PipelineMessage(
                        stream=stream,
                        message_id=mid,
                        payload=payload,
                    )
                    try:
                        await callback(msg)
                        await r.xack(stream, group, msg_id)
                    except Exception:
                        logger.exception(
                            "Error processing %s from %s/%s",
                            mid,
                            stream,
                            group,
                        )

    async def stop(self) -> None:
        self._running = False
        for task in self._consumers:
            task.cancel()
        for task in self._consumers:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consumers.clear()
        if self._redis:
            await self._redis.close()
            self._redis = None


def create_pipeline_bus(redis_url: str | None = None) -> PipelineBus:
    """Factory: return RedisStreamBus if redis_url is provided, else InProcessBus."""
    if redis_url:
        return RedisStreamBus(redis_url)
    return InProcessBus()
