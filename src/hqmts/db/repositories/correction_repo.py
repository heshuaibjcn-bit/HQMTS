"""Correction event repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.correction import CorrectionEventORM
from hqmts.db.repositories.base import BaseRepository


class CorrectionEventRepository(BaseRepository[CorrectionEventORM]):
    """Repository for correction events."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CorrectionEventORM, session)

    async def get_by_broker_trade_id(
        self, broker_trade_id: str
    ) -> list[CorrectionEventORM]:
        """Find corrections for a specific broker trade."""
        stmt = (
            select(CorrectionEventORM)
            .where(CorrectionEventORM.broker_trade_id == broker_trade_id)
            .order_by(CorrectionEventORM.detected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_unprocessed(self) -> list[CorrectionEventORM]:
        """Find all unprocessed corrections."""
        stmt = (
            select(CorrectionEventORM)
            .where(CorrectionEventORM.is_processed == False)  # noqa: E712
            .order_by(CorrectionEventORM.detected_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
