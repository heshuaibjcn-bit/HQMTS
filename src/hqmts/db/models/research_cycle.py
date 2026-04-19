"""ORM models for autonomous research cycle: ResearchCycle, FactorDiscovery, StrategyCandidate."""

from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ResearchCycleORM(Base, TimestampMixin):
    """Autonomous research cycle orchestrator (SAD 7.11)."""

    __tablename__ = "research_cycles"
    __table_args__ = (
        Index("ix_rc_status", "status"),
        Index("ix_rc_project", "research_project_id"),
    )

    research_cycle_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    opportunity_signal_json: Mapped[str] = mapped_column(Text, default="{}")

    status: Mapped[str] = mapped_column(String(32), default="opportunity_identified")

    # Link to existing research project
    research_project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Budget management
    budget_json: Mapped[str] = mapped_column(Text, default="{}")
    budget_consumed_json: Mapped[str] = mapped_column(Text, default="{}")

    # Output references
    factor_discovery_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    strategy_candidate_ids_json: Mapped[str] = mapped_column(Text, default="[]")

    # Autonomy
    autonomy_level: Mapped[str] = mapped_column(String(16), default="level_2")
    cycle_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome_reason: Mapped[str] = mapped_column(Text, default="")

    # Provenance
    source_strategy_instance_id: Mapped[str] = mapped_column(String(64), default="")
    triggered_by: Mapped[str] = mapped_column(String(64), default="")
    agent_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FactorDiscoveryORM(Base, TimestampMixin):
    """Validated factor discovery from research cycle (SAD 7.12)."""

    __tablename__ = "factor_discoveries"
    __table_args__ = (
        Index("ix_fd_cycle", "research_cycle_id"),
        Index("ix_fd_project", "research_project_id"),
        Index("ix_fd_status", "status"),
    )

    factor_discovery_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    research_cycle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    research_project_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Factor details
    factor_names_json: Mapped[str] = mapped_column(Text, default="[]")
    factor_combination: Mapped[str] = mapped_column(String(256), default="")
    discovery_type: Mapped[str] = mapped_column(String(32), default="statistical")
    description: Mapped[str] = mapped_column(Text, default="")

    # Provenance
    hypothesis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trial_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Statistical evidence
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    adjusted_alpha: Mapped[float] = mapped_column(Float, default=0.05)
    is_significant: Mapped[int] = mapped_column(Integer, default=0)  # SQLite boolean
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    # Applicability
    market_regime: Mapped[str] = mapped_column(String(32), default="")
    instrument_scope_json: Mapped[str] = mapped_column(Text, default="[]")

    status: Mapped[str] = mapped_column(String(16), default="candidate")


class StrategyCandidateORM(Base, TimestampMixin):
    """Strategy candidate generated from factor discoveries (SAD 7.13)."""

    __tablename__ = "strategy_candidates"
    __table_args__ = (
        Index("ix_sc_cycle", "research_cycle_id"),
        Index("ix_sc_status", "status"),
    )

    strategy_candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    research_cycle_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Source factors
    factor_discovery_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    source_factors_json: Mapped[str] = mapped_column(Text, default="[]")

    # Strategy definition
    strategy_template_name: Mapped[str] = mapped_column(String(64), default="")
    strategy_params_json: Mapped[str] = mapped_column(Text, default="{}")
    param_ranges_json: Mapped[str] = mapped_column(Text, default="{}")
    ai_rationale: Mapped[str] = mapped_column(Text, default="")
    signal_logic_description: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(16), default="generated")

    # Backtest results
    backtest_result_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backtest_sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    backtest_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    backtest_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    backtest_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Evaluation
    evaluation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
