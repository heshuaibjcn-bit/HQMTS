"""Position repository with domain-specific queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.position import PositionORM
from hqmts.db.repositories.base import BaseRepository


class PositionRepository(BaseRepository[PositionORM]):
    """Specialized repository for Position operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PositionORM, session)

    async def get_by_account_and_instrument(
        self, account_id: str, instrument_id: str
    ) -> PositionORM | None:
        """Get position for a specific account+instrument pair."""
        stmt = (
            select(PositionORM)
            .where(PositionORM.account_id == account_id)
            .where(PositionORM.instrument_id == instrument_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_positions_by_account(self, account_id: str) -> list[PositionORM]:
        """Get all positions for an account."""
        stmt = (
            select(PositionORM)
            .where(PositionORM.account_id == account_id)
            .order_by(PositionORM.instrument_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_open_positions(self, account_id: str) -> list[PositionORM]:
        """Get non-flat positions (total_quantity > 0) for an account."""
        stmt = (
            select(PositionORM)
            .where(PositionORM.account_id == account_id)
            .where(PositionORM.total_quantity > 0)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
