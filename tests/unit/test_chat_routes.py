"""Tests for chat API routes."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from hqmts.api.routes.chat import router as chat_router
from hqmts.core.auth import create_access_token, hash_password
from hqmts.core.enums import UserRole
from hqmts.db.base import Base
from hqmts.db.models.chat import ChatMessageORM, ChatSessionORM
from hqmts.db.models.user import UserORM

from conftest import SECRET_KEY, _make_test_settings


@pytest_asyncio.fixture
async def chat_engine():
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
async def chat_app(chat_engine):
    sf = async_sessionmaker(chat_engine, expire_on_commit=False)
    app = FastAPI()
    app.state.settings = _make_test_settings()
    app.state.db_session_factory = sf
    app.include_router(chat_router)
    return app


@pytest_asyncio.fixture
async def chat_client(chat_app):
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seeded_chat(chat_engine):
    """Seed user + other user + a chat session with messages."""
    factory = async_sessionmaker(chat_engine, expire_on_commit=False)
    async with factory() as s:
        s.add(UserORM(
            user_id="user_test001",
            username="testuser",
            password_hash=hash_password("pass"),
            role=UserRole.TRADER.value,
            display_name="Test",
            is_active=True,
        ))
        # Second user for ownership tests
        s.add(UserORM(
            user_id="user_other",
            username="otheruser",
            password_hash=hash_password("pass"),
            role=UserRole.TRADER.value,
            display_name="Other",
            is_active=True,
        ))
        s.add(ChatSessionORM(
            chat_session_id="chat_sess001",
            user_id="user_test001",
            title="Test Session",
            model_provider="openai",
            environment="research",
            status="active",
        ))
        s.add(ChatMessageORM(
            chat_message_id="msg_001",
            chat_session_id="chat_sess001",
            role="user",
            content="Hello",
        ))
        s.add(ChatMessageORM(
            chat_message_id="msg_002",
            chat_session_id="chat_sess001",
            role="assistant",
            content="Hi! How can I help?",
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


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_create_session(self, chat_client, seeded_chat):
        resp = await chat_client.post(
            "/chat/sessions",
            json={"title": "New Chat", "model_provider": "openai"},
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Chat"
        assert data["model_provider"] == "openai"
        assert data["chat_session_id"].startswith("chat_")

    @pytest.mark.asyncio
    async def test_create_session_no_auth(self, chat_client, seeded_chat):
        resp = await chat_client.post(
            "/chat/sessions",
            json={"title": "No Auth"},
        )
        assert resp.status_code == 401


class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_own_sessions(self, chat_client, seeded_chat):
        resp = await chat_client.get("/chat/sessions", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(s["chat_session_id"] == "chat_sess001" for s in data["sessions"])

    @pytest.mark.asyncio
    async def test_list_empty_for_other_user(self, chat_client, seeded_chat):
        other_token = create_access_token(
            user_id="user_other",
            role=UserRole.TRADER,
            session_id="sess_other",
            secret_key=SECRET_KEY,
        )
        resp = await chat_client.get(
            "/chat/sessions",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestGetMessages:
    @pytest.mark.asyncio
    async def test_get_messages_own_session(self, chat_client, seeded_chat):
        resp = await chat_client.get(
            "/chat/sessions/chat_sess001/messages",
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_messages_other_user_returns_404(self, chat_client, seeded_chat):
        other_token = create_access_token(
            user_id="user_other",
            role=UserRole.TRADER,
            session_id="sess_other",
            secret_key=SECRET_KEY,
        )
        resp = await chat_client.get(
            "/chat/sessions/chat_sess001/messages",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_messages_nonexistent_session(self, chat_client, seeded_chat):
        resp = await chat_client.get(
            "/chat/sessions/nonexistent/messages",
            headers=_auth_header(),
        )
        assert resp.status_code == 404


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_delete_own_session(self, chat_client, seeded_chat):
        resp = await chat_client.delete(
            "/chat/sessions/chat_sess001",
            headers=_auth_header(),
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_other_user_returns_404(self, chat_client, seeded_chat):
        other_token = create_access_token(
            user_id="user_other",
            role=UserRole.TRADER,
            session_id="sess_other",
            secret_key=SECRET_KEY,
        )
        resp = await chat_client.delete(
            "/chat/sessions/chat_sess001",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 404
