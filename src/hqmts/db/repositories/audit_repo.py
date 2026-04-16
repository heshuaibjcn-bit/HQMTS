"""AuditEvent repository with domain-specific queries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.audit import AuditEventORM
from hqmts.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEventORM]):
    """Specialized repository for AuditEvent operations.

    AuditEvents are append-only. No update or delete operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AuditEventORM, session)

    async def get_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100,
    ) -> list[AuditEventORM]:
        """Get audit events for a specific entity."""
        stmt = (
            select(AuditEventORM)
            .where(AuditEventORM.entity_type == entity_type)
            .where(AuditEventORM.entity_id == entity_id)
            .order_by(AuditEventORM.timestamp.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_time_range(
        self,
        start: datetime,
        end: datetime,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[AuditEventORM]:
        """Get audit events within a time range."""
        stmt = (
            select(AuditEventORM)
            .where(AuditEventORM.timestamp >= start)
            .where(AuditEventORM.timestamp <= end)
        )
        if event_type:
            stmt = stmt.where(AuditEventORM.event_type == event_type)
        stmt = stmt.order_by(AuditEventORM.timestamp).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_correlation_id(self, correlation_id: str) -> list[AuditEventORM]:
        """Get all audit events for a correlation ID (full trace)."""
        stmt = (
            select(AuditEventORM)
            .where(AuditEventORM.correlation_id == correlation_id)
            .order_by(AuditEventORM.timestamp)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # Override to prevent mutation on audit events
    async def update(self, entity: AuditEventORM) -> AuditEventORM:
        msg = "AuditEvent is immutable and cannot be updated"
        raise NotImplementedError(msg)

    async def delete(self, entity: AuditEventORM) -> None:
        msg = "AuditEvent is immutable and cannot be deleted"
        raise NotImplementedError(msg)
