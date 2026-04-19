"""Tests for account, alerts, and risk kill-switch API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hqmts.api.routes.alerts import router as alerts_router
from hqmts.api.routes import risk as risk_module
from hqmts.api.routes.risk import router as risk_router
from hqmts.core.auth import create_access_token, hash_password
from hqmts.core.enums import UserRole
from hqmts.db.base import Base
from hqmts.db.models.user import UserORM

TEST_USER_ID = "user_test_001"
TEST_SECRET = "change-me-in-production"


def _make_token(
    user_id: str = TEST_USER_ID,
    role: UserRole = UserRole.TRADER,
) -> str:
    return create_access_token(
        user_id=user_id,
        role=role,
        session_id="sess_test",
        secret_key=TEST_SECRET,
        expires_minutes=15,
    )


def _make_settings():
    return type("S", (), {
        "auth": type("A", (), {
            "secret_key": TEST_SECRET,
            "access_token_expire_minutes": 15,
            "refresh_token_expire_days": 7,
            "max_sessions": 3,
        })(),
    })()


async def _seed_user(session):
    """Insert a test user so get_current_user can find them."""
    user = UserORM(
        user_id=TEST_USER_ID,
        username="testuser",
        password_hash=hash_password("testpass"),
        role=UserRole.TRADER.value,
        display_name="Test User",
        is_active=True,
    )
    session.add(user)
    await session.flush()


@pytest.fixture
async def risk_app():
    """Test app with risk router and in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed test user
    async with session_factory() as session:
        await _seed_user(session)
        await session.commit()

    app = FastAPI()
    app.state.settings = _make_settings()
    app.state.db_session_factory = session_factory
    app.include_router(risk_router)

    yield app
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_kill_switch():
    """Reset in-memory kill switch state between tests."""
    risk_module._kill_switch_state.clear()
    yield
    risk_module._kill_switch_state.clear()


@pytest.fixture
async def risk_client(risk_app):
    transport = ASGITransport(app=risk_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_make_token()}"}


class TestKillSwitchActivate:
    @pytest.mark.asyncio
    async def test_activate_returns_200(self, risk_client):
        token = _make_token()
        resp = await risk_client.post(
            "/risk/kill-switch",
            json={"reason": "emergency", "account_id": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "activated"

    @pytest.mark.asyncio
    async def test_activate_without_auth_returns_401(self, risk_client):
        resp = await risk_client.post(
            "/risk/kill-switch",
            json={"reason": "emergency"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_double_activate_returns_409(self, risk_client):
        headers = _auth_headers()
        resp1 = await risk_client.post(
            "/risk/kill-switch",
            json={"reason": "emergency"},
            headers=headers,
        )
        assert resp1.status_code == 200

        resp2 = await risk_client.post(
            "/risk/kill-switch",
            json={"reason": "emergency again"},
            headers=headers,
        )
        assert resp2.status_code == 409


class TestKillSwitchDeactivate:
    @pytest.mark.asyncio
    async def test_deactivate_without_active_returns_409(self, risk_client):
        resp = await risk_client.post(
            "/risk/kill-switch/deactivate",
            json={"reason": "resume"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_activate_then_deactivate(self, risk_client):
        headers = _auth_headers()

        activate_resp = await risk_client.post(
            "/risk/kill-switch",
            json={"reason": "emergency"},
            headers=headers,
        )
        assert activate_resp.status_code == 200

        deactivate_resp = await risk_client.post(
            "/risk/kill-switch/deactivate",
            json={"reason": "resume"},
            headers=headers,
        )
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["status"] == "deactivated"


class TestKillSwitchStatus:
    @pytest.mark.asyncio
    async def test_initial_status_is_inactive(self, risk_client):
        resp = await risk_client.get("/risk/kill-switch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False

    @pytest.mark.asyncio
    async def test_status_after_activate(self, risk_client):
        await risk_client.post(
            "/risk/kill-switch",
            json={"reason": "emergency"},
            headers=_auth_headers(),
        )

        resp = await risk_client.get("/risk/kill-switch")
        assert resp.status_code == 200
        assert resp.json()["active"] is True


class TestRiskStatus:
    @pytest.mark.asyncio
    async def test_risk_status_returns_200(self, risk_client):
        resp = await risk_client.get("/risk/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "layers" in data
        assert "kill_switch_active" in data


class TestAlertsEndpoint:
    @pytest.mark.asyncio
    async def test_alerts_without_auth_returns_401(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app = FastAPI()
        app.state.settings = _make_settings()
        app.state.db_session_factory = session_factory
        app.include_router(alerts_router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/alerts")
            assert resp.status_code == 401

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_alerts_with_auth_returns_empty_list(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            await _seed_user(session)
            await session.commit()

        app = FastAPI()
        app.state.settings = _make_settings()
        app.state.db_session_factory = session_factory
        app.include_router(alerts_router)

        token = _make_token()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/alerts",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "alerts" in data
            assert isinstance(data["alerts"], list)

        await engine.dispose()
