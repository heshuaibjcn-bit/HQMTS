"""Tests for account API route."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.api.routes.account import router as account_router
from hqmts.core.auth import create_access_token, hash_password
from hqmts.core.enums import UserRole
from hqmts.db.base import Base
from hqmts.db.models.account import AccountORM
from hqmts.db.models.user import UserORM

from conftest import SECRET_KEY, _make_test_settings


@pytest_asyncio.fixture
async def account_engine():
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
async def account_app(account_engine):
    sf = async_sessionmaker(account_engine, expire_on_commit=False)
    app = FastAPI()
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = sf
    app.include_router(account_router)
    return app


@pytest_asyncio.fixture
async def account_client(account_app):
    transport = ASGITransport(app=account_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


_NOW = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def seeded_account(account_engine):
    factory = async_sessionmaker(account_engine, expire_on_commit=False)
    async with factory() as s:
        s.add(UserORM(
            user_id="user_test001",
            username="testuser",
            password_hash=hash_password("pass"),
            role=UserRole.TRADER.value,
            display_name="Test",
            is_active=True,
        ))
        s.add(AccountORM(
            account_id="acc-001",
            total_asset=1000000,
            available_cash=500000,
            frozen_cash=100000,
            market_value=400000,
            pnl_intraday=5000,
            drawdown_intraday=-2000,
            risk_status="normal",
            updated_at=_NOW,
        ))
        await s.commit()


def _auth_header(user_id="user_test001", role=UserRole.TRADER):
    token = create_access_token(
        user_id=user_id,
        role=role,
        session_id="sess_test",
        secret_key=SECRET_KEY,
        expires_minutes=15,
    )
    return {"Authorization": f"Bearer {token}"}


class TestAccountSummary:
    @pytest.mark.asyncio
    async def test_no_account_returns_defaults(self, account_client, account_engine):
        # Seed user only, no account
        factory = async_sessionmaker(account_engine, expire_on_commit=False)
        async with factory() as s:
            s.add(UserORM(
                user_id="user_test001",
                username="testuser",
                password_hash=hash_password("pass"),
                role=UserRole.TRADER.value,
                display_name="Test",
                is_active=True,
            ))
            await s.commit()
        resp = await account_client.get("/account/summary", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] is None
        assert data["total_asset"] == 0
        assert data["risk_status"] == "normal"

    @pytest.mark.asyncio
    async def test_with_account_returns_summary(self, account_client, seeded_account):
        resp = await account_client.get("/account/summary", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] == "acc-001"
        assert data["total_asset"] == 1000000.0
        assert data["available_cash"] == 500000.0
        assert data["frozen_cash"] == 100000.0

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, account_client, seeded_account):
        resp = await account_client.get("/account/summary")
        assert resp.status_code == 401
