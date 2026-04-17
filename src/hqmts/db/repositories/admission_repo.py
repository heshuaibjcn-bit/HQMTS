"""Admission repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.admission import AdmissionRecordORM
from hqmts.db.repositories.base import BaseRepository


class AdmissionRepository(BaseRepository[AdmissionRecordORM]):
    """Repository for admission records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AdmissionRecordORM, session)

    async def get_by_strategy_instance(
        self, strategy_instance_id: str
    ) -> list[AdmissionRecordORM]:
        """Get all admission records for a strategy instance."""
        stmt = (
            select(AdmissionRecordORM)
            .where(AdmissionRecordORM.strategy_instance_id == strategy_instance_id)
            .order_by(AdmissionRecordORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
