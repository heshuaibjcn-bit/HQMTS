"""Tests for deps_auth.py: get_current_user and require_role."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.api.deps_auth import check_permission, get_current_user, require_permission, require_role
from hqmts.core.auth import create_access_token, create_refresh_token, hash_password
from hqmts.core.enums import UserRole
from hqmts.db.base import Base
from hqmts.db.models.user import UserORM

from conftest import SECRET_KEY, _make_test_settings


def _make_token(**kwargs) -> str:
    defaults = {
        "user_id": "user_test001",
        "role": UserRole.TRADER,
        "session_id": "sess_test",
        "secret_key": SECRET_KEY,
        "expires_minutes": 15,
    }
    defaults.update(kwargs)
    return create_access_token(**defaults)


def _make_app_with_protected_route(engine):
    """Build app with protected routes, using StaticPool to share in-memory DB."""
    app = FastAPI()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = session_factory

    @app.get("/test/me")
    async def me(user: UserORM = Depends(get_current_user)):
        return {"user_id": user.user_id, "username": user.username, "role": user.role}

    @app.get("/test/admin-only")
    async def admin_only(user: UserORM = Depends(require_role(UserRole.SYSTEM_ADMIN))):
        return {"user_id": user.user_id}

    @app.get("/test/multi-role")
    async def multi_role(
        user: UserORM = Depends(require_role(UserRole.TRADER, UserRole.SYSTEM_ADMIN)),
    ):
        return {"user_id": user.user_id}

    return app


@pytest_asyncio.fixture
async def shared_engine():
    """In-memory engine with StaticPool so all connections share one DB."""
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
async def deps_app(shared_engine):
    return _make_app_with_protected_route(shared_engine)


@pytest_asyncio.fixture
async def deps_client(deps_app):
    transport = ASGITransport(app=deps_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seeded_deps(shared_engine):
    """Seed a test user + admin user using the shared engine."""
    factory = async_sessionmaker(shared_engine, expire_on_commit=False)
    async with factory() as s:
        s.add(UserORM(
            user_id="user_test001",
            username="testuser",
            password_hash=hash_password("pass"),
            role=UserRole.TRADER.value,
            display_name="Test",
            is_active=True,
        ))
        s.add(UserORM(
            user_id="user_admin001",
            username="admin",
            password_hash=hash_password("pass"),
            role=UserRole.SYSTEM_ADMIN.value,
            display_name="Admin",
            is_active=True,
        ))
        await s.commit()



class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401(self, deps_client, seeded_deps):
        resp = await deps_client.get("/test/me")
        assert resp.status_code == 401
        assert "Missing or invalid" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_malformed_bearer_returns_401(self, deps_client, seeded_deps):
        resp = await deps_client.get("/test/me", headers={"Authorization": "Token abc"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, deps_client, seeded_deps):
        token = _make_token(expires_minutes=-1)
        resp = await deps_client.get("/test/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self, deps_client, seeded_deps):
        token = _make_token(secret_key="wrong-secret")
        resp = await deps_client.get("/test/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_type_returns_401(self, deps_client, seeded_deps):
        refresh = create_refresh_token(
            user_id="user_test001",
            session_id="sess_test",
            secret_key=SECRET_KEY,
        )
        resp = await deps_client.get("/test/me", headers={"Authorization": f"Bearer {refresh}"})
        assert resp.status_code == 401
        assert "token type" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_missing_sub_returns_401(self, deps_client, seeded_deps):
        import jwt as pyjwt
        payload = {
            "type": "access",
            "role": "trader",
            "session_id": "sess_test",
        }
        token = pyjwt.encode(payload, SECRET_KEY, algorithm="HS256")
        resp = await deps_client.get("/test/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert "payload" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_unknown_user_returns_401(self, deps_client, seeded_deps):
        token = _make_token(user_id="user_nonexistent")
        resp = await deps_client.get("/test/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_returns_401(self, deps_client, shared_engine):
        factory = async_sessionmaker(shared_engine, expire_on_commit=False)
        async with factory() as s:
            s.add(UserORM(
                user_id="user_inactive",
                username="inactive",
                password_hash=hash_password("pass"),
                role=UserRole.TRADER.value,
                is_active=False,
            ))
            await s.commit()

        token = _make_token(user_id="user_inactive")
        resp = await deps_client.get("/test/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, deps_client, seeded_deps):
        token = _make_token()
        resp = await deps_client.get("/test/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user_test001"
        assert data["username"] == "testuser"
        assert data["role"] == UserRole.TRADER.value


class TestRequireRole:
    """Tests for require_role dependency."""

    @pytest.mark.asyncio
    async def test_role_match_passes(self, deps_client, seeded_deps):
        token = _make_token(user_id="user_admin001", role=UserRole.SYSTEM_ADMIN)
        resp = await deps_client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user_admin001"

    @pytest.mark.asyncio
    async def test_role_mismatch_returns_403(self, deps_client, seeded_deps):
        token = _make_token(role=UserRole.TRADER)
        resp = await deps_client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "not authorized" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_multi_role_match_passes(self, deps_client, seeded_deps):
        token = _make_token(role=UserRole.TRADER)
        resp = await deps_client.get("/test/multi-role", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestPermissionMatrix:
    """Tests for the role-permission matrix (PRD 30.3)."""

    def test_all_five_roles_exist(self):
        assert len(UserRole) == 5
        assert UserRole.RISK_MANAGER in UserRole
        assert UserRole.AUDITOR in UserRole

    def test_researcher_can_backtest(self):
        assert check_permission(UserRole.QUANT_RESEARCHER, "backtest", "start") is True

    def test_researcher_cannot_cancel_orders(self):
        assert check_permission(UserRole.QUANT_RESEARCHER, "orders", "cancel") is False

    def test_trader_can_cancel_orders(self):
        assert check_permission(UserRole.TRADER, "orders", "cancel") is True

    def test_risk_manager_can_kill_switch(self):
        assert check_permission(UserRole.RISK_MANAGER, "risk", "kill_switch") is True

    def test_risk_manager_can_config_risk(self):
        assert check_permission(UserRole.RISK_MANAGER, "risk", "config") is True

    def test_auditor_can_read_audit(self):
        assert check_permission(UserRole.AUDITOR, "audit", "read") is True

    def test_auditor_cannot_cancel_orders(self):
        assert check_permission(UserRole.AUDITOR, "orders", "cancel") is False

    def test_admin_has_full_risk_access(self):
        assert check_permission(UserRole.SYSTEM_ADMIN, "risk", "full") is True

    def test_unknown_feature_returns_false(self):
        assert check_permission(UserRole.SYSTEM_ADMIN, "nonexistent", "read") is False

    def test_unknown_action_returns_false(self):
        assert check_permission(UserRole.SYSTEM_ADMIN, "risk", "nonexistent") is False
