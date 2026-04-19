"""Repositories for ResearchCycle, FactorDiscovery, and StrategyCandidate."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.research_cycle import (
    FactorDiscoveryORM,
    ResearchCycleORM,
    StrategyCandidateORM,
)
from hqmts.db.repositories.base import BaseRepository


class ResearchCycleRepository(BaseRepository[ResearchCycleORM]):
    """Repository for research cycle CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ResearchCycleORM, session)

    async def get_by_cycle_id(self, cycle_id: str) -> ResearchCycleORM | None:
        return await self.get_by_id(cycle_id, "research_cycle_id")

    async def list_by_status(
        self, status: str, limit: int = 50, offset: int = 0
    ) -> list[ResearchCycleORM]:
        return await self.get_many(filters={"status": status}, limit=limit, offset=offset)


class FactorDiscoveryRepository(BaseRepository[FactorDiscoveryORM]):
    """Repository for factor discovery CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(FactorDiscoveryORM, session)

    async def get_by_discovery_id(self, discovery_id: str) -> FactorDiscoveryORM | None:
        return await self.get_by_id(discovery_id, "factor_discovery_id")

    async def list_by_cycle(
        self, cycle_id: str, limit: int = 100, offset: int = 0
    ) -> list[FactorDiscoveryORM]:
        return await self.get_many(
            filters={"research_cycle_id": cycle_id}, limit=limit, offset=offset
        )

    async def list_significant_by_cycle(
        self, cycle_id: str
    ) -> list[FactorDiscoveryORM]:
        stmt = (
            select(FactorDiscoveryORM)
            .where(FactorDiscoveryORM.research_cycle_id == cycle_id)
            .where(FactorDiscoveryORM.is_significant == 1)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class StrategyCandidateRepository(BaseRepository[StrategyCandidateORM]):
    """Repository for strategy candidate CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StrategyCandidateORM, session)

    async def get_by_candidate_id(self, candidate_id: str) -> StrategyCandidateORM | None:
        return await self.get_by_id(candidate_id, "strategy_candidate_id")

    async def list_by_cycle(
        self, cycle_id: str, limit: int = 100, offset: int = 0
    ) -> list[StrategyCandidateORM]:
        return await self.get_many(
            filters={"research_cycle_id": cycle_id}, limit=limit, offset=offset
        )

    async def list_by_status(
        self, cycle_id: str, status: str
    ) -> list[StrategyCandidateORM]:
        stmt = (
            select(StrategyCandidateORM)
            .where(StrategyCandidateORM.research_cycle_id == cycle_id)
            .where(StrategyCandidateORM.status == status)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
