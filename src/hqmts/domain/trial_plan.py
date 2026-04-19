"""TrialPlan domain model -- pre-registered experiment design."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from hqmts.core.enums import TrialPlanStatus
from hqmts.core.types import HypothesisId, ResearchProjectId, TrialPlanId


class TrialResult(BaseModel):
    """Result of executing a trial plan."""

    metric_value: float = 0.0
    metric_name: str = ""
    is_significant: bool = False
    adjusted_threshold: float = 0.0
    raw_threshold: float = 0.0
    sample_size: int = 0
    train_metric: float | None = None
    test_metric: float | None = None
    notes: str = ""

    created_at: datetime = Field(default_factory=datetime.utcnow)


class TrialPlan(BaseModel):
    """Pre-registered trial plan linked to a hypothesis."""

    trial_plan_id: TrialPlanId
    research_project_id: ResearchProjectId
    hypothesis_id: HypothesisId

    # Test design
    factor_combination: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    train_period_start: str = ""
    train_period_end: str = ""
    test_period_start: str = ""
    test_period_end: str = ""
    metric_name: str = "sharpe_ratio"
    metric_threshold: float = 0.0

    # Governance pre-registration
    trial_index_in_project: int = 0
    adjusted_alpha: float = 0.05

    # Execution state
    status: TrialPlanStatus = TrialPlanStatus.PLANNED
    result: TrialResult | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "trial_plan_id": self.trial_plan_id,
            "research_project_id": self.research_project_id,
            "hypothesis_id": self.hypothesis_id,
            "factor_combination": self.factor_combination,
            "instruments": self.instruments,
            "train_period_start": self.train_period_start,
            "train_period_end": self.train_period_end,
            "test_period_start": self.test_period_start,
            "test_period_end": self.test_period_end,
            "metric_name": self.metric_name,
            "metric_threshold": self.metric_threshold,
            "trial_index_in_project": self.trial_index_in_project,
            "adjusted_alpha": self.adjusted_alpha,
            "status": self.status.value,
            "result": self.result.model_dump() if self.result else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
