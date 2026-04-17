"""Alert repositories."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.alert import AlertAcknowledgmentORM, AlertORM


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, alert_id: str) -> AlertORM | None:
        stmt = select(AlertORM).where(AlertORM.alert_id == alert_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(
        self,
        level: str | None = None,
        acknowledged: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AlertORM]:
        stmt = select(AlertORM).order_by(AlertORM.detected_at.desc())
        if level:
            stmt = stmt.where(AlertORM.level == level)
        if acknowledged is not None:
            stmt = stmt.where(AlertORM.acknowledged == acknowledged)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, alert: AlertORM) -> AlertORM:
        self._session.add(alert)
        await self._session.flush()
        return alert

    async def mark_acknowledged(self, alert_id: str) -> None:
        stmt = (
            update(AlertORM)
            .where(AlertORM.alert_id == alert_id)
            .values(acknowledged=True)
        )
        await self._session.execute(stmt)
        await self._session.flush()


class AlertAcknowledgmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, ack: AlertAcknowledgmentORM) -> AlertAcknowledgmentORM:
        self._session.add(ack)
        await self._session.flush()
        return ack
