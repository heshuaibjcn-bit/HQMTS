"""Tests for audit middleware: _extract_entity, write-method recording, GET skip."""

from __future__ import annotations

import asyncio
import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.api.middleware.audit import AuditMiddleware, _extract_entity
from hqmts.db.base import Base
from hqmts.db.models.audit import AuditEventORM

from conftest import _make_test_settings


# ---------------------------------------------------------------------------
# Unit tests for _extract_entity (pure function, no DB needed)
# ---------------------------------------------------------------------------


class TestExtractEntity:
    """Tests for _extract_entity path parser."""

    def test_order_with_id(self):
        entity_type, entity_id = _extract_entity("/api/v1/orders/abc123")
        assert entity_type == "order"
        assert entity_id == "abc123"

    def test_order_collection(self):
        entity_type, entity_id = _extract_entity("/api/v1/orders")
        assert entity_type == "order"
        assert entity_id == ""

    def test_risk_check(self):
        entity_type, entity_id = _extract_entity("/api/v1/risk/checks/rc-42")
        assert entity_type == "risk_check"
        assert entity_id == "rc-42"

    def test_strategy_instances(self):
        entity_type, entity_id = _extract_entity("/api/v1/strategies/s1/instances")
        assert entity_type == "strategy"
        assert entity_id == "s1"

    def test_health_returns_empty(self):
        entity_type, entity_id = _extract_entity("/health")
        assert entity_type == ""
        assert entity_id == ""

    def test_signals_with_id(self):
        entity_type, entity_id = _extract_entity("/api/v1/signals/sig-001")
        assert entity_type == "signal"
        assert entity_id == "sig-001"

    def test_instruments_collection(self):
        entity_type, entity_id = _extract_entity("/api/v1/instruments")
        assert entity_type == "instrument"
        assert entity_id == ""


# ---------------------------------------------------------------------------
# Integration tests for AuditMiddleware (needs DB to verify persistence)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def audit_engine():
    """In-memory engine with StaticPool for audit tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def audit_app(audit_engine):
    """App with AuditMiddleware and dummy routes."""
    app = FastAPI()
    app.add_middleware(AuditMiddleware)
    session_factory = async_sessionmaker(audit_engine, expire_on_commit=False)
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = session_factory

    @app.post("/api/v1/orders")
    async def create_order():
        return {"id": "ord-1"}

    @app.put("/api/v1/orders/{order_id}")
    async def update_order(order_id: str):
        return {"id": order_id}

    @app.delete("/api/v1/orders/{order_id}")
    async def delete_order(order_id: str):
        return {"deleted": True}

    @app.get("/api/v1/orders")
    async def list_orders():
        return []

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest_asyncio.fixture
async def audit_client(audit_app):
    transport = ASGITransport(app=audit_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _count_audit_events(engine) -> int:
    from sqlalchemy import select, func

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await s.execute(select(func.count()).select_from(AuditEventORM))
        return result.scalar_one()


async def _get_latest_audit(engine) -> AuditEventORM:
    from sqlalchemy import select

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await s.execute(
            select(AuditEventORM).order_by(AuditEventORM.timestamp.desc()).limit(1)
        )
        return result.scalar_one()


class TestAuditMiddleware:
    """Tests for AuditMiddleware HTTP behavior."""

    @pytest.mark.asyncio
    async def test_post_creates_audit(self, audit_client, audit_engine):
        await audit_client.post("/api/v1/orders", json={"symbol": "AAPL"})
        # Give fire-and-forget task time to complete
        await asyncio.sleep(0.1)
        count = await _count_audit_events(audit_engine)
        assert count >= 1

        event = await _get_latest_audit(audit_engine)
        assert event.entity_type == "order"
        assert event.action.startswith("POST")

    @pytest.mark.asyncio
    async def test_put_creates_audit(self, audit_client, audit_engine):
        await audit_client.put("/api/v1/orders/ord-42", json={"qty": 100})
        await asyncio.sleep(0.1)
        event = await _get_latest_audit(audit_engine)
        assert event.entity_type == "order"
        assert event.entity_id == "ord-42"
        assert event.action.startswith("PUT")

    @pytest.mark.asyncio
    async def test_delete_creates_audit(self, audit_client, audit_engine):
        await audit_client.delete("/api/v1/orders/ord-99")
        await asyncio.sleep(0.1)
        event = await _get_latest_audit(audit_engine)
        assert event.entity_type == "order"
        assert event.entity_id == "ord-99"
        assert event.action.startswith("DELETE")

    @pytest.mark.asyncio
    async def test_get_no_audit(self, audit_client, audit_engine):
        await audit_client.get("/api/v1/orders")
        await asyncio.sleep(0.1)
        count = await _count_audit_events(audit_engine)
        assert count == 0

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(self, audit_client, audit_engine):
        resp = await audit_client.post(
            "/api/v1/orders",
            json={"symbol": "AAPL"},
            headers={"X-Correlation-ID": "corr-test-123"},
        )
        await asyncio.sleep(0.1)
        assert resp.headers.get("X-Correlation-ID") == "corr-test-123"

        event = await _get_latest_audit(audit_engine)
        assert event.correlation_id == "corr-test-123"

    @pytest.mark.asyncio
    async def test_correlation_id_generated_if_missing(self, audit_client, audit_engine):
        resp = await audit_client.post("/api/v1/orders", json={"symbol": "AAPL"})
        await asyncio.sleep(0.1)
        # Should have a generated UUID in response header
        corr_id = resp.headers.get("X-Correlation-ID")
        assert corr_id is not None
        assert len(corr_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_details_json_contains_status_and_duration(self, audit_client, audit_engine):
        await audit_client.post("/api/v1/orders", json={"symbol": "AAPL"})
        await asyncio.sleep(0.1)
        event = await _get_latest_audit(audit_engine)
        details = json.loads(event.details_json)
        assert details["status_code"] == 200
        assert "duration_ms" in details
