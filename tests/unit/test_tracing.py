"""Tests for structured tracing (RequestIdMiddleware, trace context)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hqmts.infra.tracing import (
    RequestIdMiddleware,
    bind_trace_context,
    clear_trace_context,
)
import structlog


@pytest.fixture
def trace_app():
    """Minimal FastAPI app with RequestIdMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


class TestRequestIdMiddleware:
    @pytest.mark.asyncio
    async def test_generates_request_id(self, trace_app):
        transport = ASGITransport(app=trace_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert "X-Request-ID" in resp.headers
            uid = resp.headers["X-Request-ID"]
            assert len(uid) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_reuses_provided_request_id(self, trace_app):
        transport = ASGITransport(app=trace_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/health",
                headers={"X-Request-ID": "my-req-123"},
            )
            assert resp.headers["X-Request-ID"] == "my-req-123"

    @pytest.mark.asyncio
    async def test_unique_ids_per_request(self, trace_app):
        transport = ASGITransport(app=trace_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.get("/health")
            resp2 = await client.get("/health")
            id1 = resp1.headers["X-Request-ID"]
            id2 = resp2.headers["X-Request-ID"]
            assert id1 != id2  # Each request gets a unique ID


class TestTraceContext:
    def test_bind_and_clear(self):
        bind_trace_context(
            request_id="r1",
            correlation_id="c1",
            signal_id="sig-001",
        )
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("request_id") == "r1"
        assert ctx.get("correlation_id") == "c1"
        assert ctx.get("signal_id") == "sig-001"

        clear_trace_context()
        ctx = structlog.contextvars.get_contextvars()
        assert ctx == {}

    def test_bind_extra_fields(self):
        bind_trace_context(order_id="ord-123", step="risk_check")
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("order_id") == "ord-123"
        assert ctx.get("step") == "risk_check"

        clear_trace_context()

    def test_bind_no_args_is_noop(self):
        clear_trace_context()
        bind_trace_context()
        ctx = structlog.contextvars.get_contextvars()
        assert ctx == {}
