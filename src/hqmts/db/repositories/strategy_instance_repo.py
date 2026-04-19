"""StrategyInstance repository with domain-specific queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import StrategyStatus
from hqmts.db.models.strategy import StrategyInstanceORM
from hqmts.db.repositories.base import BaseRepository


class StrategyInstanceRepository(BaseRepository[StrategyInstanceORM]):
    """Specialized repository for StrategyInstance operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StrategyInstanceORM, session)

    async def get_active_by_account(self, account_id: str) -> list[StrategyInstanceORM]:
        """Get all active strategy instances for an account."""
        active_statuses = [
            StrategyStatus.LIVE_RUNNING.value,
            StrategyStatus.PAUSE_OPEN.value,
            StrategyStatus.CLOSE_ONLY.value,
            StrategyStatus.PAUSED.value,
            StrategyStatus.PAPER_RUNNING.value,
        ]
        stmt = (
            select(StrategyInstanceORM)
            .where(StrategyInstanceORM.account_id == account_id)
            .where(StrategyInstanceORM.status.in_(active_statuses))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_environment(self, environment: str) -> list[StrategyInstanceORM]:
        """Get all strategy instances for a specific environment."""
        stmt = (
            select(StrategyInstanceORM)
            .where(StrategyInstanceORM.environment == environment)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> list[StrategyInstanceORM]:
        """Get all strategy instances with a specific status."""
        stmt = (
            select(StrategyInstanceORM)
            .where(StrategyInstanceORM.status == status)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
