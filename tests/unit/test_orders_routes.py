"""Tests for orders API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.api.routes.orders import router as orders_router
from hqmts.db.base import Base
from hqmts.db.models.order import OrderORM

from conftest import _make_test_settings


@pytest_asyncio.fixture
async def orders_engine():
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
async def orders_app(orders_engine):
    session_factory = async_sessionmaker(orders_engine, expire_on_commit=False)

    app = FastAPI()
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = session_factory
    app.include_router(orders_router)
    return app


@pytest_asyncio.fixture
async def orders_client(orders_app):
    transport = ASGITransport(app=orders_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seeded_orders(orders_engine):
    factory = async_sessionmaker(orders_engine, expire_on_commit=False)
    async with factory() as s:
        now = datetime.now(timezone.utc)
        s.add(OrderORM(
            order_id="ord-001",
            account_id="acc-001",
            instrument_id="600000.SH",
            side="buy",
            price=Decimal("10.50"),
            quantity=100,
            filled_quantity=100,
            status="filled",
            order_type="limit",
            broker_order_id="brk-001",
            created_at=now,
            updated_at=now,
        ))
        s.add(OrderORM(
            order_id="ord-002",
            account_id="acc-001",
            instrument_id="000001.SZ",
            side="sell",
            price=Decimal("25.00"),
            quantity=200,
            filled_quantity=0,
            status="pending",
            order_type="limit",
            created_at=now,
            updated_at=now,
        ))
        s.add(OrderORM(
            order_id="ord-003",
            account_id="acc-002",
            instrument_id="600000.SH",
            side="buy",
            price=Decimal("10.60"),
            quantity=50,
            filled_quantity=0,
            status="rejected",
            order_type="market",
            reject_reason="insufficient funds",
            created_at=now,
            updated_at=now,
        ))
        await s.commit()


class TestListOrders:
    @pytest.mark.asyncio
    async def test_empty_list(self, orders_client):
        resp = await orders_client.get("/orders/")
        if resp.status_code != 200:
            print("BODY:", resp.text)
        assert resp.status_code == 200
        data = resp.json()
        assert data["orders"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_all_orders(self, orders_client, seeded_orders):
        resp = await orders_client.get("/orders/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["orders"]) == 3

    @pytest.mark.asyncio
    async def test_filter_by_account(self, orders_client, seeded_orders):
        resp = await orders_client.get("/orders/", params={"account_id": "acc-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(o["account_id"] == "acc-001" for o in data["orders"])

    @pytest.mark.asyncio
    async def test_filter_by_instrument(self, orders_client, seeded_orders):
        resp = await orders_client.get("/orders/", params={"instrument_id": "600000.SH"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(o["instrument_id"] == "600000.SH" for o in data["orders"])

    @pytest.mark.asyncio
    async def test_filter_by_status(self, orders_client, seeded_orders):
        resp = await orders_client.get("/orders/", params={"status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["orders"][0]["order_id"] == "ord-002"

    @pytest.mark.asyncio
    async def test_serialization_fields(self, orders_client, seeded_orders):
        resp = await orders_client.get("/orders/", params={"limit": 1})
        assert resp.status_code == 200
        order = resp.json()["orders"][0]
        assert "order_id" in order
        assert "account_id" in order
        assert "price" in order
        assert "status" in order
        assert "created_at" in order


class TestGetOrder:
    @pytest.mark.asyncio
    async def test_existing_order(self, orders_client, seeded_orders):
        resp = await orders_client.get("/orders/ord-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["order_id"] == "ord-001"
        assert data["side"] == "buy"
        assert data["price"] == "10.5000"

    @pytest.mark.asyncio
    async def test_nonexistent_order_returns_404(self, orders_client, seeded_orders):
        resp = await orders_client.get("/orders/ord-nonexistent")
        assert resp.status_code == 404
