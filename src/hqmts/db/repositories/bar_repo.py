"""Bar data repository for persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import Cycle
from hqmts.core.types import InstrumentId
from hqmts.db.base import Base
from hqmts.db.models.bar import BarORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.domain.bar import Bar


class BarRepository(BaseRepository[BarORM]):
    """Repository for Bar CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(BarORM, session)

    async def get_bars_by_instrument_cycle(
        self,
        instrument_id: InstrumentId,
        cycle: Cycle,
        start: datetime,
        end: datetime,
        completed_only: bool = True,
    ) -> list[Bar]:
        """Get bars for an instrument/cycle within a time range."""
        stmt = (
            select(BarORM)
            .where(
                BarORM.instrument_id == str(instrument_id),
                BarORM.cycle == cycle.value,
                BarORM.bar_start_time >= start,
                BarORM.bar_start_time < end,
            )
            .order_by(BarORM.bar_start_time)
        )
        if completed_only:
            stmt = stmt.where(BarORM.is_completed == True)  # noqa: E712
        result = await self._session.execute(stmt)
        return [_orm_to_bar(orm) for orm in result.scalars().all()]

    async def get_latest_bar(
        self,
        instrument_id: InstrumentId,
        cycle: Cycle,
    ) -> Bar | None:
        """Get the most recent bar for an instrument/cycle."""
        stmt = (
            select(BarORM)
            .where(
                BarORM.instrument_id == str(instrument_id),
                BarORM.cycle == cycle.value,
            )
            .order_by(BarORM.bar_start_time.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _orm_to_bar(orm) if orm else None

    async def bulk_upsert(self, bars: Sequence[Bar]) -> int:
        """Insert bars, skipping duplicates (by instrument_id, cycle, bar_start_time).

        Uses INSERT ... ON CONFLICT for PostgreSQL, check-and-insert for SQLite.
        Returns the number of bars actually inserted.
        """
        if not bars:
            return 0

        inserted = 0
        for bar in bars:
            orm = _bar_to_orm(bar)
            # Check if already exists
            stmt = select(BarORM).where(
                BarORM.instrument_id == orm.instrument_id,
                BarORM.cycle == orm.cycle,
                BarORM.bar_start_time == orm.bar_start_time,
                BarORM.data_version == orm.data_version,
            )
            result = await self._session.execute(stmt)
            if result.scalar_one_or_none() is None:
                self._session.add(orm)
                inserted += 1

        await self._session.flush()
        return inserted


def _bar_to_orm(bar: Bar) -> BarORM:
    """Convert Bar domain object to BarORM."""
    return BarORM(
        instrument_id=str(bar.instrument_id),
        cycle=bar.cycle.value,
        bar_start_time=bar.bar_start_time,
        bar_end_time=bar.bar_end_time,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        amount=bar.amount,
        is_completed=bar.is_completed,
        source=bar.source,
        data_version=str(bar.data_version),
        quality=bar.quality.value,
    )


def _orm_to_bar(orm: BarORM) -> Bar:
    """Convert BarORM to Bar domain object."""
    from hqmts.core.enums import DataQualityGrade
    from hqmts.core.types import VersionStr

    return Bar(
        instrument_id=InstrumentId(orm.instrument_id),
        cycle=Cycle(orm.cycle),
        bar_start_time=orm.bar_start_time,
        bar_end_time=orm.bar_end_time,
        open=orm.open,
        high=orm.high,
        low=orm.low,
        close=orm.close,
        volume=orm.volume,
        amount=orm.amount,
        is_completed=orm.is_completed,
        source=orm.source,
        data_version=VersionStr(orm.data_version),
        quality=DataQualityGrade(orm.quality) if orm.quality else DataQualityGrade.PASS,
    )
