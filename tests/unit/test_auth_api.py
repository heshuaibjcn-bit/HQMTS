"""Tests for auth API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hqmts.api.app import create_app
from hqmts.api.routes.auth import router as auth_router
from hqmts.core.auth import create_access_token, hash_password
from hqmts.core.enums import UserRole
from hqmts.db.base import Base


@pytest.fixture
async def test_app():
    """Create a minimal test app with auth routes and in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.state.settings = type("S", (), {
        "auth": type("A", (), {
            "secret_key": "change-me-in-production",
            "access_token_expire_minutes": 15,
            "refresh_token_expire_days": 7,
            "max_sessions": 3,
        })(),
    })()
    app.state.db_session_factory = session_factory
    app.include_router(auth_router)

    yield app
    await engine.dispose()


@pytest.fixture
async def client(test_app):
    """Async HTTP test client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_access_token(
    user_id: str = "user_001",
    role: UserRole = UserRole.TRADER,
    session_id: str = "sess_test",
    secret_key: str = "change-me-in-production",
) -> str:
    return create_access_token(
        user_id=user_id,
        role=role,
        session_id=session_id,
        secret_key=secret_key,
        expires_minutes=15,
    )


class TestLoginEndpoint:
    @pytest.mark.asyncio
    async def test_login_missing_fields_returns_422(self, client):
        """Missing fields return validation error."""
        resp = await client.post("/auth/login", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(self, client):
        """Wrong username/password returns 401."""
        resp = await client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "wrong"},
        )
        assert resp.status_code == 401


class TestMeEndpoint:
    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(self, client):
        """No auth header returns 401."""
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_invalid_token_returns_401(self, client):
        """Invalid token returns 401."""
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_expired_token_returns_401(self, client):
        """Expired token returns 401."""
        token = create_access_token(
            user_id="user_001",
            role=UserRole.TRADER,
            session_id="sess_test",
            secret_key="change-me-in-production",
            expires_minutes=-1,
        )
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


class TestRefreshEndpoint:
    @pytest.mark.asyncio
    async def test_refresh_invalid_token_returns_401(self, client):
        """Invalid refresh token returns 401."""
        resp = await client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401


class TestLogoutEndpoint:
    @pytest.mark.asyncio
    async def test_logout_without_token_returns_401(self, client):
        """No auth header returns 401."""
        resp = await client.post("/auth/logout")
        assert resp.status_code == 401
