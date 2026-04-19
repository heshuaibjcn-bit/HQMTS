"""Research project orchestrator -- manages 6-stage lifecycle.

Coordinates project creation, stage advancement, hypothesis management,
trial plan execution, and report generation.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import (
    HypothesisStatus,
    ResearchProjectStatus,
    ResearchMode,
    TrialPlanStatus,
)
from hqmts.core.types import HypothesisId, ResearchProjectId, TrialPlanId
from hqmts.db.models.research_project import (
    HypothesisORM,
    ResearchProjectORM,
    TrialPlanORM,
)
from hqmts.db.repositories.research_repo import (
    HypothesisRepository,
    ResearchProjectRepository,
    TrialPlanRepository,
)
from hqmts.domain.hypothesis import Hypothesis
from hqmts.domain.research_project import ResearchProject
from hqmts.domain.trial_plan import TrialPlan, TrialResult
from hqmts.research.governance import MultipleTestingGovernance
from hqmts.statemachine.research_project_fsm import research_project_fsm


def _json_list(value: str) -> list[str]:
    """Parse a JSON array string, returning empty list on failure."""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


class ResearchOrchestrator:
    """Core service orchestrating the research project lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._project_repo = ResearchProjectRepository(session)
        self._hypothesis_repo = HypothesisRepository(session)
        self._trial_repo = TrialPlanRepository(session)
        # Per-project governance sessions (in-memory cache, keyed by project_id)
        self._governance_sessions: dict[str, MultipleTestingGovernance] = {}

    # ── Project CRUD ────────────────────────────────────────────────────────────

    async def create_project(
        self,
        title: str,
        research_question: str,
        instrument_ids: list[str] | None = None,
        factor_categories: list[str] | None = None,
        time_range_start: str = "",
        time_range_end: str = "",
        cycle: str = "1d",
        trial_budget: int = 100,
        mode: str = "collaborative",
        created_by: str = "",
    ) -> ResearchProject:
        """Create a new research project in CREATED state."""
        project_id = ResearchProjectId(f"rp_{uuid.uuid4().hex[:12]}")
        project = ResearchProject(
            research_project_id=project_id,
            title=title,
            research_question=research_question,
            instrument_ids=instrument_ids or [],
            factor_categories=factor_categories or [],
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            cycle=cycle,
            trial_budget=trial_budget,
            mode=ResearchMode(mode),
            created_by=created_by,
        )

        orm = ResearchProjectORM(
            research_project_id=project.research_project_id,
            title=project.title,
            research_question=project.research_question,
            status=project.status.value,
            current_stage=project.current_stage,
            instrument_ids=json.dumps(project.instrument_ids),
            factor_categories=json.dumps(project.factor_categories),
            time_range_start=project.time_range_start,
            time_range_end=project.time_range_end,
            cycle=project.cycle,
            governance_session_id=project.governance_session_id,
            agent_task_id=project.agent_task_id,
            trial_budget=project.trial_budget,
            hypothesis_ids=json.dumps(project.hypothesis_ids),
            trial_ids=json.dumps(project.trial_ids),
            report_id=project.report_id,
            created_by=project.created_by,
            mode=project.mode.value,
        )
        await self._project_repo.create(orm)

        # Initialize per-project governance
        self._governance_sessions[project_id] = MultipleTestingGovernance(
            alpha=0.05, method="bonferroni", max_trials=trial_budget,
        )

        return project

    async def get_project(self, project_id: str) -> ResearchProject | None:
        """Get a research project by ID."""
        orm = await self._project_repo.get_by_project_id(project_id)
        if orm is None:
            return None
        return self._orm_to_project(orm)

    async def list_projects(
        self, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> tuple[list[ResearchProject], int]:
        """List projects with optional status filter. Returns (list, total)."""
        filters = {"status": status} if status else None
        orms = await self._project_repo.get_many(filters=filters, limit=limit, offset=offset)
        total = await self._project_repo.count(filters=filters)
        return [self._orm_to_project(o) for o in orms], total

    async def cancel_project(self, project_id: str) -> ResearchProject:
        """Cancel a project."""
        return await self._advance_status(project_id, ResearchProjectStatus.CANCELED)

    # ── Stage Advancement ──────────────────────────────────────────────────────

    async def advance_stage(self, project_id: str) -> ResearchProject:
        """Advance project to the next stage in the lifecycle.

        Validates prerequisites before advancing.
        """
        project = await self.get_project(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        current = ResearchProjectStatus(project.status)
        stage_map: dict[ResearchProjectStatus, ResearchProjectStatus] = {
            ResearchProjectStatus.CREATED: ResearchProjectStatus.EXPLORING,
            ResearchProjectStatus.EXPLORING: ResearchProjectStatus.HYPOTHESIZING,
            ResearchProjectStatus.HYPOTHESIZING: ResearchProjectStatus.DESIGNING,
            ResearchProjectStatus.DESIGNING: ResearchProjectStatus.EXECUTING,
            ResearchProjectStatus.EXECUTING: ResearchProjectStatus.VALIDATING,
            ResearchProjectStatus.VALIDATING: ResearchProjectStatus.REPORTING,
            ResearchProjectStatus.REPORTING: ResearchProjectStatus.COMPLETED,
        }
        target = stage_map.get(current)
        if target is None:
            raise ValueError(f"Cannot advance from terminal state {current.value}")

        # Prerequisite checks
        if current == ResearchProjectStatus.HYPOTHESIZING:
            hypotheses = await self._hypothesis_repo.list_by_status(project_id, "accepted")
            if not hypotheses:
                raise ValueError("Cannot advance: need at least 1 accepted hypothesis")

        if current == ResearchProjectStatus.DESIGNING:
            trials = await self._trial_repo.list_by_project(project_id)
            planned = [t for t in trials if t.status == "planned"]
            if not planned:
                raise ValueError("Cannot advance: need at least 1 planned trial")

        return await self._advance_status(project_id, target)

    async def rollback_to_executing(self, project_id: str) -> ResearchProject:
        """Roll back from validating to executing (re-run trials)."""
        return await self._advance_status(project_id, ResearchProjectStatus.EXECUTING)

    # ── Hypothesis Management ──────────────────────────────────────────────────

    async def create_hypothesis(
        self,
        project_id: str,
        prediction: str = "",
        factor_names: list[str] | None = None,
        target_metric: str = "sharpe_ratio",
        expected_effect: str = "positive",
        expected_magnitude: float = 0.0,
        instrument_scope: list[str] | None = None,
        ai_rationale: str = "",
        confidence: float = 0.5,
        created_by: str = "ai",
    ) -> Hypothesis:
        """Create a new hypothesis for a project."""
        hypothesis_id = HypothesisId(f"hyp_{uuid.uuid4().hex[:12]}")
        hypothesis = Hypothesis(
            hypothesis_id=hypothesis_id,
            research_project_id=project_id,
            prediction=prediction,
            factor_names=factor_names or [],
            target_metric=target_metric,
            expected_effect=expected_effect,
            expected_magnitude=expected_magnitude,
            instrument_scope=instrument_scope or [],
            ai_rationale=ai_rationale,
            confidence=confidence,
            created_by=created_by,
        )

        orm = HypothesisORM(
            hypothesis_id=hypothesis.hypothesis_id,
            research_project_id=hypothesis.research_project_id,
            version=hypothesis.version,
            prediction=hypothesis.prediction,
            factor_names=json.dumps(hypothesis.factor_names),
            target_metric=hypothesis.target_metric,
            expected_effect=hypothesis.expected_effect,
            expected_magnitude=hypothesis.expected_magnitude,
            instrument_scope=json.dumps(hypothesis.instrument_scope),
            market_regime=hypothesis.market_regime,
            time_period=hypothesis.time_period,
            ai_rationale=hypothesis.ai_rationale,
            human_rationale=hypothesis.human_rationale,
            supporting_evidence=hypothesis.supporting_evidence,
            confidence=hypothesis.confidence,
            priority=hypothesis.priority,
            status=hypothesis.status.value,
            created_by=hypothesis.created_by,
        )
        await self._hypothesis_repo.create(orm)

        # Add to project's hypothesis_ids
        project_orm = await self._project_repo.get_by_project_id(project_id)
        if project_orm:
            ids = _json_list(project_orm.hypothesis_ids)
            ids.append(hypothesis_id)
            project_orm.hypothesis_ids = json.dumps(ids)
            await self._project_repo.update(project_orm)

        return hypothesis

    async def update_hypothesis_status(
        self, hypothesis_id: str, status: str, human_rationale: str = "",
    ) -> Hypothesis | None:
        """Accept, reject, or modify a hypothesis."""
        orm = await self._hypothesis_repo.get_by_hypothesis_id(hypothesis_id)
        if orm is None:
            return None
        orm.status = status
        if human_rationale:
            orm.human_rationale = human_rationale
        await self._hypothesis_repo.update(orm)
        return self._orm_to_hypothesis(orm)

    async def list_hypotheses(self, project_id: str) -> list[Hypothesis]:
        """List all hypotheses for a project."""
        orms = await self._hypothesis_repo.list_by_project(project_id)
        return [self._orm_to_hypothesis(o) for o in orms]

    # ── Trial Plan Management ──────────────────────────────────────────────────

    async def create_trial_plan(
        self,
        project_id: str,
        hypothesis_id: str,
        factor_combination: list[str] | None = None,
        instruments: list[str] | None = None,
        train_period_start: str = "",
        train_period_end: str = "",
        test_period_start: str = "",
        test_period_end: str = "",
        metric_name: str = "sharpe_ratio",
        metric_threshold: float = 0.0,
    ) -> TrialPlan:
        """Create a pre-registered trial plan for a hypothesis."""
        # Get adjusted alpha from project governance
        governance = self._get_governance(project_id)
        adjusted_alpha = governance.get_adjusted_threshold()
        trial_count = await self._trial_repo.count_by_project(project_id)

        trial_plan_id = TrialPlanId(f"tp_{uuid.uuid4().hex[:12]}")
        plan = TrialPlan(
            trial_plan_id=trial_plan_id,
            research_project_id=project_id,
            hypothesis_id=hypothesis_id,
            factor_combination=factor_combination or [],
            instruments=instruments or [],
            train_period_start=train_period_start,
            train_period_end=train_period_end,
            test_period_start=test_period_start,
            test_period_end=test_period_end,
            metric_name=metric_name,
            metric_threshold=metric_threshold,
            trial_index_in_project=trial_count + 1,
            adjusted_alpha=adjusted_alpha,
        )

        orm = TrialPlanORM(
            trial_plan_id=plan.trial_plan_id,
            research_project_id=plan.research_project_id,
            hypothesis_id=plan.hypothesis_id,
            factor_combination=json.dumps(plan.factor_combination),
            instruments=json.dumps(plan.instruments),
            train_period_start=plan.train_period_start,
            train_period_end=plan.train_period_end,
            test_period_start=plan.test_period_start,
            test_period_end=plan.test_period_end,
            metric_name=plan.metric_name,
            metric_threshold=plan.metric_threshold,
            trial_index_in_project=plan.trial_index_in_project,
            adjusted_alpha=plan.adjusted_alpha,
            status=plan.status.value,
        )
        await self._trial_repo.create(orm)

        # Add to project's trial_ids
        project_orm = await self._project_repo.get_by_project_id(project_id)
        if project_orm:
            ids = _json_list(project_orm.trial_ids)
            ids.append(trial_plan_id)
            project_orm.trial_ids = json.dumps(ids)
            await self._project_repo.update(project_orm)

        return plan

    async def execute_trial(self, trial_plan_id: str) -> TrialResult:
        """Execute a trial plan: compute factor values and evaluate.

        In production this would trigger actual factor computation.
        For now, creates a placeholder result.
        """
        orm = await self._trial_repo.get_by_trial_id(trial_plan_id)
        if orm is None:
            raise ValueError(f"Trial plan {trial_plan_id} not found")
        if orm.status != "planned":
            raise ValueError(f"Trial plan is in {orm.status} state, cannot execute")

        orm.status = "running"
        await self._trial_repo.update(orm)

        # Record with governance
        governance = self._get_governance(orm.research_project_id)
        governance.record_trial(
            factor_name=",".join(_json_list(orm.factor_combination)[:3]),
            strategy_name=f"trial_{orm.trial_index_in_project}",
            metric_name=orm.metric_name,
            metric_value=0.0,  # placeholder, real computation would fill this
            threshold=orm.metric_threshold,
        )

        result = TrialResult(
            metric_name=orm.metric_name,
            adjusted_threshold=governance.get_adjusted_threshold(),
            raw_threshold=orm.metric_threshold,
            notes="Trial executed (placeholder result).",
        )

        orm.status = "completed"
        orm.result_json = json.dumps(result.model_dump())
        await self._trial_repo.update(orm)

        return result

    async def list_trial_plans(self, project_id: str) -> list[TrialPlan]:
        """List all trial plans for a project."""
        orms = await self._trial_repo.list_by_project(project_id)
        return [self._orm_to_trial_plan(o) for o in orms]

    # ── Governance ─────────────────────────────────────────────────────────────

    def _get_governance(self, project_id: str) -> MultipleTestingGovernance:
        """Get or create governance session for a project."""
        if project_id not in self._governance_sessions:
            self._governance_sessions[project_id] = MultipleTestingGovernance(
                alpha=0.05, method="bonferroni", max_trials=100,
            )
        return self._governance_sessions[project_id]

    async def get_governance_stats(self, project_id: str) -> dict[str, Any]:
        """Get governance stats for a specific project."""
        governance = self._get_governance(project_id)
        stats = governance.compute_stats()
        return {
            **stats.to_dict(),
            "adjusted_threshold": governance.get_adjusted_threshold(),
            "budget_remaining": governance._max_trials - governance.trial_count,
            "budget_total": governance._max_trials,
        }

    # ── Internal Helpers ───────────────────────────────────────────────────────

    async def _advance_status(
        self, project_id: str, target: ResearchProjectStatus,
    ) -> ResearchProject:
        """Advance project status via state machine."""
        orm = await self._project_repo.get_by_project_id(project_id)
        if orm is None:
            raise ValueError(f"Project {project_id} not found")

        current = ResearchProjectStatus(orm.status)
        new_status = research_project_fsm.transition(current, target)
        orm.status = new_status.value

        # Update current_stage based on status
        stage_map = {
            ResearchProjectStatus.CREATED: "exploration",
            ResearchProjectStatus.EXPLORING: "exploration",
            ResearchProjectStatus.HYPOTHESIZING: "hypothesis",
            ResearchProjectStatus.DESIGNING: "design",
            ResearchProjectStatus.EXECUTING: "execution",
            ResearchProjectStatus.VALIDATING: "validation",
            ResearchProjectStatus.REPORTING: "report",
            ResearchProjectStatus.COMPLETED: "completed",
            ResearchProjectStatus.FAILED: "failed",
            ResearchProjectStatus.CANCELED: "canceled",
        }
        orm.current_stage = stage_map.get(new_status, orm.current_stage)
        await self._project_repo.update(orm)
        return self._orm_to_project(orm)

    @staticmethod
    def _orm_to_project(orm: ResearchProjectORM) -> ResearchProject:
        return ResearchProject(
            research_project_id=orm.research_project_id,
            title=orm.title,
            research_question=orm.research_question,
            status=ResearchProjectStatus(orm.status),
            current_stage=orm.current_stage,
            instrument_ids=_json_list(orm.instrument_ids),
            factor_categories=_json_list(orm.factor_categories),
            time_range_start=orm.time_range_start,
            time_range_end=orm.time_range_end,
            cycle=orm.cycle,
            governance_session_id=orm.governance_session_id,
            agent_task_id=orm.agent_task_id,
            trial_budget=orm.trial_budget,
            hypothesis_ids=_json_list(orm.hypothesis_ids),
            trial_ids=_json_list(orm.trial_ids),
            report_id=orm.report_id,
            created_by=orm.created_by,
            mode=ResearchMode(orm.mode),
        )

    @staticmethod
    def _orm_to_hypothesis(orm: HypothesisORM) -> Hypothesis:
        return Hypothesis(
            hypothesis_id=orm.hypothesis_id,
            research_project_id=orm.research_project_id,
            version=orm.version,
            prediction=orm.prediction,
            factor_names=_json_list(orm.factor_names),
            target_metric=orm.target_metric,
            expected_effect=orm.expected_effect,
            expected_magnitude=orm.expected_magnitude,
            instrument_scope=_json_list(orm.instrument_scope),
            market_regime=orm.market_regime,
            time_period=orm.time_period,
            ai_rationale=orm.ai_rationale,
            human_rationale=orm.human_rationale,
            supporting_evidence=orm.supporting_evidence,
            confidence=orm.confidence,
            priority=orm.priority,
            status=HypothesisStatus(orm.status),
            created_by=orm.created_by,
        )

    @staticmethod
    def _orm_to_trial_plan(orm: TrialPlanORM) -> TrialPlan:
        result = None
        if orm.result_json:
            try:
                result = TrialResult(**json.loads(orm.result_json))
            except (json.JSONDecodeError, TypeError):
                pass
        return TrialPlan(
            trial_plan_id=orm.trial_plan_id,
            research_project_id=orm.research_project_id,
            hypothesis_id=orm.hypothesis_id,
            factor_combination=_json_list(orm.factor_combination),
            instruments=_json_list(orm.instruments),
            train_period_start=orm.train_period_start,
            train_period_end=orm.train_period_end,
            test_period_start=orm.test_period_start,
            test_period_end=orm.test_period_end,
            metric_name=orm.metric_name,
            metric_threshold=orm.metric_threshold,
            trial_index_in_project=orm.trial_index_in_project,
            adjusted_alpha=orm.adjusted_alpha,
            status=TrialPlanStatus(orm.status),
            result=result,
        )
