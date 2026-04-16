"""CashReservation repository with domain-specific queries."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import ReservationStatus
from hqmts.db.models.reservation import CashReservationORM
from hqmts.db.repositories.base import BaseRepository


class ReservationRepository(BaseRepository[CashReservationORM]):
    """Specialized repository for CashReservation operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CashReservationORM, session)

    async def get_active_by_account(self, account_id: str) -> list[CashReservationORM]:
        """Get all active reservations for an account."""
        stmt = (
            select(CashReservationORM)
            .where(CashReservationORM.account_id == account_id)
            .where(CashReservationORM.status == ReservationStatus.ACTIVE.value)
            .order_by(CashReservationORM.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_total_reserved_amount(self, account_id: str) -> Decimal:
        """Get total reserved amount for active reservations on an account."""
        stmt = (
            select(func.coalesce(func.sum(CashReservationORM.reserved_amount), 0))
            .where(CashReservationORM.account_id == account_id)
            .where(CashReservationORM.status == ReservationStatus.ACTIVE.value)
        )
        result = await self._session.execute(stmt)
        return Decimal(str(result.scalar_one()))

    async def get_expired_reservations(self, now: datetime) -> list[CashReservationORM]:
        """Get reservations that have passed their expiry time."""
        stmt = (
            select(CashReservationORM)
            .where(CashReservationORM.status == ReservationStatus.ACTIVE.value)
            .where(CashReservationORM.expires_at < now)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_execution_intent(self, execution_intent_id: str) -> CashReservationORM | None:
        """Get reservation by execution intent ID."""
        stmt = select(CashReservationORM).where(
            CashReservationORM.execution_intent_id == execution_intent_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
