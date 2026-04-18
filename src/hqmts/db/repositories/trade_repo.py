"""Trade repository with domain-specific queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.trade import TradeORM
from hqmts.db.repositories.base import BaseRepository


class TradeRepository(BaseRepository[TradeORM]):
    """Specialized repository for Trade operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TradeORM, session)

    async def get_by_broker_trade_id(self, broker_trade_id: str) -> TradeORM | None:
        """Find trade by broker-assigned trade ID (dedup lookup)."""
        stmt = select(TradeORM).where(TradeORM.broker_trade_id == broker_trade_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_trades_by_order(self, order_id: str) -> list[TradeORM]:
        """Get all fills for a given order."""
        stmt = (
            select(TradeORM)
            .where(TradeORM.order_id == order_id)
            .order_by(TradeORM.traded_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_trades_by_instrument(
        self, instrument_id: str, limit: int = 100
    ) -> list[TradeORM]:
        """Get recent trades for an instrument."""
        stmt = (
            select(TradeORM)
            .where(TradeORM.instrument_id == instrument_id)
            .order_by(TradeORM.traded_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
