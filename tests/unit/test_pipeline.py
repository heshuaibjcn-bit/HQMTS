"""Tests for the async pipeline bus (InProcessBus)."""

from __future__ import annotations

import asyncio

import pytest

from hqmts.infra.pipeline import (
    STREAM_ORDERS,
    STREAM_SIGNALS,
    InProcessBus,
    PipelineMessage,
    create_pipeline_bus,
)


@pytest.fixture
def bus() -> InProcessBus:
    return InProcessBus()


class TestInProcessBus:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self, bus: InProcessBus):
        """Published messages should be received by subscribers."""
        received: list[PipelineMessage] = []

        async def handler(msg: PipelineMessage):
            received.append(msg)

        await bus.subscribe(STREAM_SIGNALS, "test-group", handler)
        await bus.start()

        msg_id = await bus.publish(STREAM_SIGNALS, {"signal_id": "sig-001", "side": "buy"})
        assert msg_id

        # Wait for the consumer to process
        await asyncio.sleep(0.3)

        assert len(received) == 1
        assert received[0].payload["signal_id"] == "sig-001"
        assert received[0].stream == STREAM_SIGNALS

        await bus.stop()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, bus: InProcessBus):
        """Multiple subscribers on the same stream each get the messages."""
        received_a: list[PipelineMessage] = []
        received_b: list[PipelineMessage] = []

        async def handler_a(msg: PipelineMessage):
            received_a.append(msg)

        async def handler_b(msg: PipelineMessage):
            received_b.append(msg)

        await bus.subscribe(STREAM_ORDERS, "group-a", handler_a)
        await bus.subscribe(STREAM_ORDERS, "group-b", handler_b)
        await bus.start()

        await bus.publish(STREAM_ORDERS, {"order_id": "ord-001"})
        await asyncio.sleep(0.3)

        # Both groups should receive the message
        assert len(received_a) == 1
        assert len(received_b) == 1

        await bus.stop()

    @pytest.mark.asyncio
    async def test_no_cross_stream_delivery(self, bus: InProcessBus):
        """Messages on one stream should NOT be delivered to another stream's subscribers."""
        received: list[PipelineMessage] = []

        async def handler(msg: PipelineMessage):
            received.append(msg)

        await bus.subscribe(STREAM_SIGNALS, "sig-group", handler)
        await bus.start()

        # Publish to a different stream
        await bus.publish(STREAM_ORDERS, {"order_id": "ord-002"})
        await asyncio.sleep(0.3)

        assert len(received) == 0

        await bus.stop()

    @pytest.mark.asyncio
    async def test_consumer_error_does_not_crash(self, bus: InProcessBus):
        """A failing callback should not crash the consumer loop."""
        received: list[PipelineMessage] = []
        call_count = 0

        async def bad_handler(msg: PipelineMessage):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("boom")
            received.append(msg)

        await bus.subscribe(STREAM_SIGNALS, "bad-group", bad_handler)
        await bus.start()

        await bus.publish(STREAM_SIGNALS, {"signal_id": "sig-bad-1"})
        await bus.publish(STREAM_SIGNALS, {"signal_id": "sig-bad-2"})
        await asyncio.sleep(0.5)

        # Second message should still be processed despite first failure
        assert call_count == 2
        assert len(received) == 1

        await bus.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_consumers(self, bus: InProcessBus):
        """Stop should cancel all consumer tasks."""
        async def noop(msg: PipelineMessage):
            pass

        await bus.subscribe(STREAM_SIGNALS, "g1", noop)
        await bus.start()
        assert len(bus._consumers) == 1

        await bus.stop()
        assert len(bus._consumers) == 0


class TestCreatePipelineBus:
    def test_no_redis_returns_inprocess(self):
        bus = create_pipeline_bus(None)
        assert isinstance(bus, InProcessBus)

    def test_empty_string_returns_inprocess(self):
        bus = create_pipeline_bus("")
        assert isinstance(bus, InProcessBus)

    def test_redis_url_returns_redis_stream_bus(self):
        from hqmts.infra.pipeline import RedisStreamBus

        bus = create_pipeline_bus("redis://localhost:6379/0")
        assert isinstance(bus, RedisStreamBus)
