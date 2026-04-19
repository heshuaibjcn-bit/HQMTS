"""ResearchCycle domain model -- autonomous research cycle orchestrator (SAD 7.11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from hqmts.core.enums import AutonomyLevel, CycleOutcome, ResearchCycleStatus
from hqmts.core.types import (
    AgentTaskId,
    FactorDiscoveryId,
    ResearchCycleId,
    ResearchProjectId,
    StrategyCandidateId,
    StrategyInstanceId,
)


class ResearchCycleBudget(BaseModel):
    """Budget configuration for a research cycle."""

    max_trials: int = 100
    max_compute_hours: float = 10.0
    max_llm_tokens: int = 1_000_000


class ResearchCycleBudgetConsumed(BaseModel):
    """Budget consumed so far."""

    trials_used: int = 0
    compute_hours_used: float = 0.0
    llm_tokens_used: int = 0


class ResearchCycle(BaseModel):
    """Autonomous research cycle orchestrator (SAD 7.11).

    Manages the full lifecycle from opportunity identification through
    factor discovery, synthesis, backtesting, and evaluation.
    """

    model_config = {"frozen": False}

    research_cycle_id: ResearchCycleId
    title: str
    opportunity_type: str = ""
    opportunity_signal_json: str = "{}"

    status: ResearchCycleStatus = ResearchCycleStatus.OPPORTUNITY_IDENTIFIED

    research_project_id: ResearchProjectId | None = None

    # Budget management
    budget_json: str = "{}"
    budget_consumed_json: str = "{}"

    # Output references
    factor_discovery_ids_json: str = "[]"
    strategy_candidate_ids_json: str = "[]"

    # Autonomy
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_2
    cycle_outcome: CycleOutcome | None = None
    outcome_reason: str = ""

    # Provenance
    source_strategy_instance_id: StrategyInstanceId = ""
    triggered_by: str = ""
    agent_task_id: AgentTaskId | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_terminal(self) -> bool:
        """Check if cycle is in a terminal state."""
        return self.status in {
            ResearchCycleStatus.PROMOTED,
            ResearchCycleStatus.ARCHIVED,
            ResearchCycleStatus.CANCELED,
            ResearchCycleStatus.FAILED,
        }

    def to_dict(self) -> dict:
        return {
            "research_cycle_id": self.research_cycle_id,
            "title": self.title,
            "opportunity_type": self.opportunity_type,
            "status": self.status.value,
            "research_project_id": self.research_project_id,
            "autonomy_level": self.autonomy_level.value,
            "cycle_outcome": self.cycle_outcome.value if self.cycle_outcome else None,
            "outcome_reason": self.outcome_reason,
            "factor_discovery_ids_json": self.factor_discovery_ids_json,
            "strategy_candidate_ids_json": self.strategy_candidate_ids_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FactorDiscovery(BaseModel):
    """Validated factor discovery from research cycle (SAD 7.12)."""

    model_config = {"frozen": False}

    factor_discovery_id: FactorDiscoveryId
    research_cycle_id: ResearchCycleId
    research_project_id: ResearchProjectId

    # Factor details
    factor_names_json: str = "[]"
    factor_combination: str = ""
    discovery_type: str = "statistical"
    description: str = ""

    # Provenance
    hypothesis_id: str | None = None
    trial_plan_id: str | None = None

    # Statistical evidence
    metric_value: float = 0.0
    adjusted_alpha: float = 0.05
    is_significant: bool = False
    confidence: float = 0.5

    # Applicability
    market_regime: str = ""
    instrument_scope_json: str = "[]"

    status: str = "candidate"  # FactorDiscoveryStatus

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "factor_discovery_id": self.factor_discovery_id,
            "research_cycle_id": self.research_cycle_id,
            "research_project_id": self.research_project_id,
            "factor_names_json": self.factor_names_json,
            "factor_combination": self.factor_combination,
            "discovery_type": self.discovery_type,
            "description": self.description,
            "metric_value": self.metric_value,
            "adjusted_alpha": self.adjusted_alpha,
            "is_significant": self.is_significant,
            "confidence": self.confidence,
            "market_regime": self.market_regime,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StrategyCandidate(BaseModel):
    """Strategy candidate generated from factor discoveries (SAD 7.13)."""

    model_config = {"frozen": False}

    strategy_candidate_id: StrategyCandidateId
    research_cycle_id: ResearchCycleId

    # Source factors
    factor_discovery_ids_json: str = "[]"
    source_factors_json: str = "[]"

    # Strategy definition
    strategy_template_name: str = ""
    strategy_params_json: str = "{}"
    param_ranges_json: str = "{}"
    ai_rationale: str = ""
    signal_logic_description: str = ""

    status: str = "generated"  # StrategyCandidateStatus

    # Backtest results
    backtest_result_ref: str | None = None
    backtest_sharpe: float | None = None
    backtest_return: float | None = None
    backtest_drawdown: float | None = None
    backtest_trades: int | None = None

    # Evaluation
    evaluation_score: float | None = None
    evaluation_verdict: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "strategy_candidate_id": self.strategy_candidate_id,
            "research_cycle_id": self.research_cycle_id,
            "factor_discovery_ids_json": self.factor_discovery_ids_json,
            "source_factors_json": self.source_factors_json,
            "strategy_template_name": self.strategy_template_name,
            "ai_rationale": self.ai_rationale,
            "status": self.status,
            "backtest_sharpe": self.backtest_sharpe,
            "backtest_return": self.backtest_return,
            "backtest_drawdown": self.backtest_drawdown,
            "backtest_trades": self.backtest_trades,
            "evaluation_score": self.evaluation_score,
            "evaluation_verdict": self.evaluation_verdict,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
