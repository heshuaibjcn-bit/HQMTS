"""Tests for strategies API routes."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.api.routes.strategies import router as strategies_router
from hqmts.db.base import Base
from hqmts.db.models.strategy import StrategyORM, StrategyInstanceORM

from conftest import _make_test_settings


@pytest_asyncio.fixture
async def strategies_engine():
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
async def strategies_app(strategies_engine):
    session_factory = async_sessionmaker(strategies_engine, expire_on_commit=False)

    app = FastAPI()
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = session_factory
    app.include_router(strategies_router)
    return app


@pytest_asyncio.fixture
async def strategies_client(strategies_app):
    transport = ASGITransport(app=strategies_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seeded_strategies(strategies_engine):
    factory = async_sessionmaker(strategies_engine, expire_on_commit=False)
    async with factory() as s:
        s.add(StrategyORM(
            strategy_id="strat-001",
            name="Momentum Alpha",
            version="1.0.0",
            description="Momentum strategy for A-shares",
            supported_cycles='["5m","1h"]',
            status="active",
        ))
        s.add(StrategyORM(
            strategy_id="strat-002",
            name="Mean Reversion",
            version="2.1.0",
            description="Mean reversion strategy",
            supported_cycles='["1d"]',
            status="draft",
        ))
        s.add(StrategyInstanceORM(
            strategy_instance_id="si-001",
            strategy_id="strat-001",
            strategy_version="1.0.0",
            environment="research",
            status="running",
            params_json='{"lookback": 20}',
            instruments_json='["600000.SH"]',
        ))
        s.add(StrategyInstanceORM(
            strategy_instance_id="si-002",
            strategy_id="strat-001",
            strategy_version="1.0.0",
            environment="production",
            status="running",
            params_json='{"lookback": 10}',
            instruments_json='["000001.SZ"]',
        ))
        await s.commit()


class TestListStrategies:
    @pytest.mark.asyncio
    async def test_empty_list(self, strategies_client):
        resp = await strategies_client.get("/strategies/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategies"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_all_strategies(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get("/strategies/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["strategies"]) == 2

    @pytest.mark.asyncio
    async def test_filter_by_status(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get("/strategies/", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["strategies"][0]["strategy_id"] == "strat-001"

    @pytest.mark.asyncio
    async def test_serialization_fields(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get("/strategies/", params={"limit": 1})
        assert resp.status_code == 200
        strat = resp.json()["strategies"][0]
        assert "strategy_id" in strat
        assert "name" in strat
        assert "version" in strat
        assert "created_at" in strat


class TestGetStrategy:
    @pytest.mark.asyncio
    async def test_existing_strategy(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get("/strategies/strat-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy_id"] == "strat-001"
        assert data["name"] == "Momentum Alpha"

    @pytest.mark.asyncio
    async def test_nonexistent_strategy_returns_404(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get("/strategies/strat-nonexistent")
        assert resp.status_code == 404


class TestListStrategyInstances:
    @pytest.mark.asyncio
    async def test_instances_for_strategy(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get("/strategies/strat-001/instances")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["instances"]) == 2
        assert all(i["strategy_id"] == "strat-001" for i in data["instances"])

    @pytest.mark.asyncio
    async def test_filter_by_environment(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get(
            "/strategies/strat-001/instances", params={"environment": "research"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["instances"]) == 1
        assert data["instances"][0]["environment"] == "research"

    @pytest.mark.asyncio
    async def test_empty_instances_for_unknown_strategy(self, strategies_client, seeded_strategies):
        resp = await strategies_client.get("/strategies/strat-nonexistent/instances")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instances"] == []
