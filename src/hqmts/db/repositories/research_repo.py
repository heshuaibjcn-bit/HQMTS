"""Repositories for ResearchProject, Hypothesis, and TrialPlan."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.research_project import (
    HypothesisORM,
    ResearchProjectORM,
    TrialPlanORM,
    TrialResultORM,
)
from hqmts.db.repositories.base import BaseRepository


class ResearchProjectRepository(BaseRepository[ResearchProjectORM]):
    """Repository for research project CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ResearchProjectORM, session)

    async def get_by_project_id(self, project_id: str) -> ResearchProjectORM | None:
        return await self.get_by_id(project_id, "research_project_id")

    async def list_by_status(
        self, status: str, limit: int = 50, offset: int = 0
    ) -> list[ResearchProjectORM]:
        return await self.get_many(filters={"status": status}, limit=limit, offset=offset)

    async def list_by_creator(
        self, created_by: str, limit: int = 50, offset: int = 0
    ) -> list[ResearchProjectORM]:
        return await self.get_many(filters={"created_by": created_by}, limit=limit, offset=offset)


class HypothesisRepository(BaseRepository[HypothesisORM]):
    """Repository for hypothesis CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(HypothesisORM, session)

    async def get_by_hypothesis_id(self, hypothesis_id: str) -> HypothesisORM | None:
        return await self.get_by_id(hypothesis_id, "hypothesis_id")

    async def list_by_project(
        self, project_id: str, limit: int = 100, offset: int = 0
    ) -> list[HypothesisORM]:
        return await self.get_many(
            filters={"research_project_id": project_id}, limit=limit, offset=offset
        )

    async def list_by_status(
        self, project_id: str, status: str
    ) -> list[HypothesisORM]:
        stmt = (
            select(HypothesisORM)
            .where(HypothesisORM.research_project_id == project_id)
            .where(HypothesisORM.status == status)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class TrialPlanRepository(BaseRepository[TrialPlanORM]):
    """Repository for trial plan CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TrialPlanORM, session)

    async def get_by_trial_id(self, trial_id: str) -> TrialPlanORM | None:
        return await self.get_by_id(trial_id, "trial_plan_id")

    async def list_by_project(
        self, project_id: str, limit: int = 100, offset: int = 0
    ) -> list[TrialPlanORM]:
        return await self.get_many(
            filters={"research_project_id": project_id}, limit=limit, offset=offset
        )

    async def list_by_hypothesis(
        self, hypothesis_id: str, limit: int = 100, offset: int = 0
    ) -> list[TrialPlanORM]:
        return await self.get_many(
            filters={"hypothesis_id": hypothesis_id}, limit=limit, offset=offset
        )

    async def count_by_project(self, project_id: str) -> int:
        return await self.count(filters={"research_project_id": project_id})
