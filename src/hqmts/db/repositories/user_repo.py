"""User and session repositories."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.user import SessionORM, UserORM


class UserRepository:
    """Async repository for UserORM."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> UserORM | None:
        stmt = select(UserORM).where(UserORM.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> UserORM | None:
        stmt = select(UserORM).where(UserORM.username == username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: UserORM) -> UserORM:
        self._session.add(user)
        await self._session.flush()
        return user


class SessionRepository:
    """Async repository for SessionORM."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session_obj: SessionORM) -> SessionORM:
        self._session.add(session_obj)
        await self._session.flush()
        return session_obj

    async def get_by_id(self, session_id: str) -> SessionORM | None:
        stmt = select(SessionORM).where(SessionORM.session_id == session_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_sessions(self, user_id: str) -> list[SessionORM]:
        stmt = (
            select(SessionORM)
            .where(SessionORM.user_id == user_id, SessionORM.status == "active")
            .order_by(SessionORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_session(self, session_id: str) -> None:
        stmt = (
            update(SessionORM)
            .where(SessionORM.session_id == session_id)
            .values(status="revoked")
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def revoke_all_user_sessions(self, user_id: str) -> None:
        stmt = (
            update(SessionORM)
            .where(SessionORM.user_id == user_id, SessionORM.status == "active")
            .values(status="revoked")
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def count_active_sessions(self, user_id: str) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(SessionORM).where(
            SessionORM.user_id == user_id, SessionORM.status == "active",
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
