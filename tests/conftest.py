"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hqmts.core.auth import create_access_token, hash_password
from hqmts.core.enums import UserRole
from hqmts.db.base import Base
from hqmts.db.models.user import UserORM
from hqmts.infra.config import Settings, load_settings

SECRET_KEY = "change-me-in-production"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    """Load Settings for the research environment."""
    return load_settings("research")


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """In-memory SQLite async session for integration tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


# --- Auth test fixtures ---


def _make_test_settings():
    return type("S", (), {
        "auth": type("A", (), {
            "secret_key": SECRET_KEY,
            "access_token_expire_minutes": 15,
            "refresh_token_expire_days": 7,
            "max_sessions": 3,
        })(),
    })()


@pytest_asyncio.fixture
async def auth_engine():
    """Create an in-memory engine with all tables for auth tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_session(auth_engine):
    """AsyncSession with a seeded test user."""
    factory = async_sessionmaker(auth_engine, expire_on_commit=False)
    async with factory() as s:
        user = UserORM(
            user_id="user_test001",
            username="testuser",
            password_hash=hash_password("testpass123"),
            role=UserRole.TRADER.value,
            display_name="Test User",
            is_active=True,
        )
        s.add(user)
        await s.commit()
        yield s


def _make_token(
    user_id: str = "user_test001",
    role: UserRole = UserRole.TRADER,
    session_id: str = "sess_test",
    secret_key: str = SECRET_KEY,
    expires_minutes: int = 15,
) -> str:
    return create_access_token(
        user_id=user_id,
        role=role,
        session_id=session_id,
        secret_key=secret_key,
        expires_minutes=expires_minutes,
    )


def _build_auth_app(auth_engine, *routers):
    """Build a FastAPI app with auth middleware and given routers."""
    from hqmts.api.deps import get_db

    session_factory = async_sessionmaker(auth_engine, expire_on_commit=False)

    async def _get_db(request):
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app = FastAPI()
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = session_factory
    app.dependency_overrides[get_db] = _get_db
    for router in routers:
        app.include_router(router)
    return app


@pytest_asyncio.fixture
async def authed_client(auth_engine, seeded_session):
    """AsyncClient with a pre-authenticated trader user."""
    from hqmts.api.routes.auth import router as auth_router

    app = _build_auth_app(auth_engine, auth_router)
    token = _make_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


@pytest_asyncio.fixture
async def admin_client(auth_engine):
    """AsyncClient with a pre-authenticated admin user."""
    from hqmts.api.routes.auth import router as auth_router

    factory = async_sessionmaker(auth_engine, expire_on_commit=False)
    async with factory() as s:
        admin = UserORM(
            user_id="user_admin001",
            username="admin",
            password_hash=hash_password("adminpass"),
            role=UserRole.SYSTEM_ADMIN.value,
            display_name="Admin",
            is_active=True,
        )
        s.add(admin)
        await s.commit()

    app = _build_auth_app(auth_engine, auth_router)
    token = _make_token(user_id="user_admin001", role=UserRole.SYSTEM_ADMIN)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
