"""Account repository with domain-specific queries."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.account import AccountORM
from hqmts.db.repositories.base import BaseRepository


class AccountRepository(BaseRepository[AccountORM]):
    """Specialized repository for Account operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AccountORM, session)

    async def update_risk_status(self, account_id: str, risk_status: str) -> None:
        """Update the risk_status field on an account."""
        stmt = (
            update(AccountORM)
            .where(AccountORM.account_id == account_id)
            .values(risk_status=risk_status)
        )
        await self._session.execute(stmt)
        await self._session.flush()
