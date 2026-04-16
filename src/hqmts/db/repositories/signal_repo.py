"""Signal repository with domain-specific queries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.signal import SignalORM
from hqmts.db.repositories.base import BaseRepository


class SignalRepository(BaseRepository[SignalORM]):
    """Specialized repository for Signal operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SignalORM, session)

    async def get_by_strategy_instance(
        self,
        strategy_instance_id: str,
        limit: int = 100,
    ) -> list[SignalORM]:
        """Get signals for a strategy instance, newest first."""
        stmt = (
            select(SignalORM)
            .where(SignalORM.strategy_instance_id == strategy_instance_id)
            .order_by(SignalORM.decision_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_time_range(
        self,
        strategy_instance_id: str,
        start: datetime,
        end: datetime,
    ) -> list[SignalORM]:
        """Get signals within a time range for a strategy instance."""
        stmt = (
            select(SignalORM)
            .where(SignalORM.strategy_instance_id == strategy_instance_id)
            .where(SignalORM.decision_time >= start)
            .where(SignalORM.decision_time <= end)
            .order_by(SignalORM.decision_time)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_instrument(
        self,
        instrument_id: str,
        limit: int = 50,
    ) -> list[SignalORM]:
        """Get recent signals for an instrument."""
        stmt = (
            select(SignalORM)
            .where(SignalORM.instrument_id == instrument_id)
            .order_by(SignalORM.decision_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
