"""Tests for signals API routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.api.routes.signals import router as signals_router
from hqmts.db.base import Base
from hqmts.db.models.signal import SignalORM

from conftest import _make_test_settings


@pytest_asyncio.fixture
async def signals_engine():
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
async def signals_app(signals_engine):
    session_factory = async_sessionmaker(signals_engine, expire_on_commit=False)

    app = FastAPI()
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = session_factory
    app.include_router(signals_router)
    return app


@pytest_asyncio.fixture
async def signals_client(signals_app):
    transport = ASGITransport(app=signals_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


_NOW = datetime.now(timezone.utc)
_VALID_UNTIL = _NOW + timedelta(hours=4)


@pytest_asyncio.fixture
async def seeded_signals(signals_engine):
    factory = async_sessionmaker(signals_engine, expire_on_commit=False)
    async with factory() as s:
        s.add(SignalORM(
            signal_id="sig-001",
            strategy_instance_id="si-alpha",
            strategy_version="1.0.0",
            decision_time=_NOW,
            instrument_id="600000.SH",
            signal_type="entry",
            target_direction="long",
            valid_until=_VALID_UNTIL,
            cycle="5m",
        ))
        s.add(SignalORM(
            signal_id="sig-002",
            strategy_instance_id="si-alpha",
            strategy_version="1.0.0",
            decision_time=_NOW,
            instrument_id="000001.SZ",
            signal_type="exit",
            target_direction="short",
            valid_until=_VALID_UNTIL,
            cycle="1m",
        ))
        s.add(SignalORM(
            signal_id="sig-003",
            strategy_instance_id="si-beta",
            strategy_version="2.0.0",
            decision_time=_NOW,
            instrument_id="600000.SH",
            signal_type="entry",
            target_direction="long",
            valid_until=_VALID_UNTIL,
            cycle="5m",
        ))
        await s.commit()


class TestListSignals:
    @pytest.mark.asyncio
    async def test_empty_list(self, signals_client):
        resp = await signals_client.get("/signals/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["signals"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_all_signals(self, signals_client, seeded_signals):
        resp = await signals_client.get("/signals/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["signals"]) == 3

    @pytest.mark.asyncio
    async def test_filter_by_strategy_instance(self, signals_client, seeded_signals):
        resp = await signals_client.get("/signals/", params={"strategy_instance_id": "si-alpha"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(s["strategy_instance_id"] == "si-alpha" for s in data["signals"])

    @pytest.mark.asyncio
    async def test_filter_by_instrument(self, signals_client, seeded_signals):
        resp = await signals_client.get("/signals/", params={"instrument_id": "600000.SH"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2


class TestGetSignal:
    @pytest.mark.asyncio
    async def test_existing_signal(self, signals_client, seeded_signals):
        resp = await signals_client.get("/signals/sig-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal_id"] == "sig-001"
        assert data["instrument_id"] == "600000.SH"

    @pytest.mark.asyncio
    async def test_nonexistent_signal_returns_404(self, signals_client, seeded_signals):
        resp = await signals_client.get("/signals/sig-nonexistent")
        assert resp.status_code == 404
