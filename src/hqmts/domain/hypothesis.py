"""Hypothesis domain model -- structured research hypothesis with provenance."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import HypothesisStatus
from hqmts.core.types import HypothesisId, ResearchProjectId


class Hypothesis(BaseModel):
    """A structured, versioned research hypothesis."""

    hypothesis_id: HypothesisId
    research_project_id: ResearchProjectId
    version: int = 1

    # Structured hypothesis fields
    prediction: str = ""
    factor_names: list[str] = Field(default_factory=list)
    target_metric: str = "sharpe_ratio"
    expected_effect: str = "positive"
    expected_magnitude: float = 0.0

    # Conditions
    instrument_scope: list[str] = Field(default_factory=list)
    market_regime: str | None = None
    time_period: str | None = None

    # Rationale
    ai_rationale: str = ""
    human_rationale: str = ""
    supporting_evidence: str = ""

    # Governance
    confidence: float = 0.5
    priority: int = 0
    status: HypothesisStatus = HypothesisStatus.DRAFT

    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "ai"

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "research_project_id": self.research_project_id,
            "version": self.version,
            "prediction": self.prediction,
            "factor_names": self.factor_names,
            "target_metric": self.target_metric,
            "expected_effect": self.expected_effect,
            "expected_magnitude": self.expected_magnitude,
            "instrument_scope": self.instrument_scope,
            "market_regime": self.market_regime,
            "time_period": self.time_period,
            "ai_rationale": self.ai_rationale,
            "human_rationale": self.human_rationale,
            "supporting_evidence": self.supporting_evidence,
            "confidence": self.confidence,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }
