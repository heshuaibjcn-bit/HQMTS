"""Chat session and message repositories."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.chat import ChatMessageORM, ChatSessionORM


class ChatSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: str) -> ChatSessionORM | None:
        stmt = select(ChatSessionORM).where(ChatSessionORM.chat_session_id == session_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_sessions(
        self, user_id: str, limit: int = 50, offset: int = 0,
    ) -> list[ChatSessionORM]:
        stmt = (
            select(ChatSessionORM)
            .where(ChatSessionORM.user_id == user_id)
            .order_by(ChatSessionORM.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, chat_session: ChatSessionORM) -> ChatSessionORM:
        self._session.add(chat_session)
        await self._session.flush()
        return chat_session

    async def update_status(self, session_id: str, status: str) -> None:
        stmt = (
            update(ChatSessionORM)
            .where(ChatSessionORM.chat_session_id == session_id)
            .values(status=status)
        )
        await self._session.execute(stmt)
        await self._session.flush()


class ChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, message: ChatMessageORM) -> ChatMessageORM:
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_session_messages(
        self, chat_session_id: str, limit: int = 50, offset: int = 0,
    ) -> list[ChatMessageORM]:
        stmt = (
            select(ChatMessageORM)
            .where(ChatMessageORM.chat_session_id == chat_session_id)
            .order_by(ChatMessageORM.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
