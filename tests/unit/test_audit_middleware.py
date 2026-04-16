"""Tests for AuditMiddleware persistence."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hqmts.api.middleware.audit import AuditMiddleware, _extract_entity
from hqmts.db.base import Base
from hqmts.db.repositories.audit_repo import AuditRepository


# ---------------------------------------------------------------------------
# Unit tests for _extract_entity helper
# ---------------------------------------------------------------------------


class TestExtractEntity:
    def test_orders_with_id(self):
        et, eid = _extract_entity("/api/v1/orders/ord-123")
        assert et == "order"
        assert eid == "ord-123"

    def test_orders_collection(self):
        et, eid = _extract_entity("/api/v1/orders")
        assert et == "order"
        assert eid == ""

    def test_strategies_with_id(self):
        et, eid = _extract_entity("/api/v1/strategies/strat-1")
        assert et == "strategy"
        assert eid == "strat-1"

    def test_strategies_with_instances(self):
        et, eid = _extract_entity("/api/v1/strategies/s1/instances")
        assert et == "strategy"
        assert eid == "s1"

    def test_risk_checks_with_id(self):
        et, eid = _extract_entity("/api/v1/risk/checks/rc-42")
        assert et == "risk_check"
        assert eid == "rc-42"

    def test_signals_collection(self):
        et, eid = _extract_entity("/api/v1/signals")
        assert et == "signal"
        assert eid == ""

    def test_health_endpoint(self):
        et, eid = _extract_entity("/health")
        assert et == ""
        assert eid == ""

    def test_instruments_with_id(self):
        et, eid = _extract_entity("/instruments/000001.SZ")
        assert et == "instrument"
        assert eid == "000001.SZ"

    def test_audit_events(self):
        et, eid = _extract_entity("/api/v1/audit/events")
        assert et == "audit_event"
        assert eid == ""


# ---------------------------------------------------------------------------
# Integration test: middleware persists audit events on write requests
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_app():
    """Minimal FastAPI app with audit middleware + in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.add_middleware(AuditMiddleware)
    app.state.db_session_factory = session_factory
    app.state._env = "test"

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/orders/{order_id}")
    async def get_order(order_id: str):
        return {"order_id": order_id}

    @app.get("/orders")
    async def list_orders():
        return {"orders": []}

    yield app, session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_post_creates_audit_event(test_app):
    """A POST request should result in an AuditEventORM row in the DB."""
    app, session_factory = test_app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/orders",
            json={"test": "data"},
            headers={"X-Correlation-ID": "corr-mw-test", "X-Actor": "tester"},
        )
        assert "X-Correlation-ID" in resp.headers
        assert resp.headers["X-Correlation-ID"] == "corr-mw-test"

    # Give fire-and-forget task time to complete
    await asyncio.sleep(0.2)

    async with session_factory() as session:
        repo = AuditRepository(session)
        events = await repo.get_by_correlation_id("corr-mw-test")
        assert len(events) >= 1
        event = events[0]
        assert event.event_type == "api_request"
        assert event.actor == "tester"
        assert event.action.startswith("POST")
        assert event.entity_type == "order"


@pytest.mark.asyncio
async def test_get_does_not_create_audit_event(test_app):
    """GET requests should NOT create audit events."""
    app, session_factory = test_app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get(
            "/health",
            headers={"X-Correlation-ID": "corr-get-test"},
        )

    await asyncio.sleep(0.1)

    async with session_factory() as session:
        repo = AuditRepository(session)
        events = await repo.get_by_correlation_id("corr-get-test")
        assert len(events) == 0


@pytest.mark.asyncio
async def test_delete_with_entity_id(test_app):
    """DELETE /orders/{id} should extract entity_id from path."""
    app, session_factory = test_app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.delete(
            "/orders/ord-del-001",
            headers={"X-Correlation-ID": "corr-del-test"},
        )

    await asyncio.sleep(0.2)

    async with session_factory() as session:
        repo = AuditRepository(session)
        events = await repo.get_by_correlation_id("corr-del-test")
        assert len(events) >= 1
        assert events[0].entity_id == "ord-del-001"
        assert events[0].entity_type == "order"
