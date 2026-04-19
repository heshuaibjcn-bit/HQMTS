"""Order repository with domain-specific queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import OrderStatus
from hqmts.db.models.order import OrderORM
from hqmts.db.repositories.base import BaseRepository


class OrderRepository(BaseRepository[OrderORM]):
    """Specialized repository for Order operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OrderORM, session)

    async def get_by_broker_order_id(self, broker_order_id: str) -> OrderORM | None:
        """Find order by broker-assigned order ID."""
        stmt = select(OrderORM).where(OrderORM.broker_order_id == broker_order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_orders_by_account(self, account_id: str) -> list[OrderORM]:
        """Get all non-terminal orders for an account."""
        active_statuses = [
            OrderStatus.CREATED.value,
            OrderStatus.PENDING_SUBMIT.value,
            OrderStatus.SUBMITTED.value,
            OrderStatus.ACCEPTED.value,
            OrderStatus.PARTIAL_FILLED.value,
            OrderStatus.SUSPENDED.value,
            OrderStatus.ERROR.value,
        ]
        stmt = (
            select(OrderORM)
            .where(OrderORM.account_id == account_id)
            .where(OrderORM.status.in_(active_statuses))
            .order_by(OrderORM.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_instrument(self, instrument_id: str, limit: int = 50) -> list[OrderORM]:
        """Get recent orders for an instrument."""
        stmt = (
            select(OrderORM)
            .where(OrderORM.instrument_id == instrument_id)
            .order_by(OrderORM.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_conflicting_inflight_orders(
        self,
        account_id: str,
        instrument_id: str,
        side: str,
    ) -> bool:
        """Check if there are conflicting in-flight orders for the same instrument/side."""
        active_statuses = [
            OrderStatus.CREATED.value,
            OrderStatus.PENDING_SUBMIT.value,
            OrderStatus.SUBMITTED.value,
            OrderStatus.ACCEPTED.value,
            OrderStatus.PARTIAL_FILLED.value,
            OrderStatus.SUSPENDED.value,
            OrderStatus.ERROR.value,
        ]
        stmt = (
            select(OrderORM)
            .where(OrderORM.account_id == account_id)
            .where(OrderORM.instrument_id == instrument_id)
            .where(OrderORM.side == side)
            .where(OrderORM.status.in_(active_statuses))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
