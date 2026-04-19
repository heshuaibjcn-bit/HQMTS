"""ORM models for factor research workflow: ResearchProject, Hypothesis, TrialPlan."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ResearchProjectORM(Base, TimestampMixin):
    """Research project orchestrator with 6-stage lifecycle."""

    __tablename__ = "research_projects"
    __table_args__ = (
        Index("ix_rp_status", "status"),
        Index("ix_rp_mode", "mode"),
        Index("ix_rp_created_by", "created_by"),
    )

    research_project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    research_question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="created")
    current_stage: Mapped[str] = mapped_column(String(20), default="exploration")

    # Research scope
    instrument_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    factor_categories: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    time_range_start: Mapped[str] = mapped_column(String(20), default="")
    time_range_end: Mapped[str] = mapped_column(String(20), default="")
    cycle: Mapped[str] = mapped_column(String(8), default="1d")

    # Governance linkage
    governance_session_id: Mapped[str] = mapped_column(String(64), default="")
    agent_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trial_budget: Mapped[int] = mapped_column(Integer, default=100)

    # Output references
    hypothesis_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    trial_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    report_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Metadata
    created_by: Mapped[str] = mapped_column(String(64), default="")
    mode: Mapped[str] = mapped_column(String(20), default="collaborative")


class HypothesisORM(Base, TimestampMixin):
    """Structured research hypothesis with provenance."""

    __tablename__ = "hypotheses"
    __table_args__ = (
        Index("ix_hyp_project", "research_project_id"),
        Index("ix_hyp_status", "status"),
    )

    hypothesis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    research_project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Structured hypothesis fields
    prediction: Mapped[str] = mapped_column(Text, default="")
    factor_names: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    target_metric: Mapped[str] = mapped_column(String(32), default="sharpe_ratio")
    expected_effect: Mapped[str] = mapped_column(String(16), default="positive")
    expected_magnitude: Mapped[float] = mapped_column(Float, default=0.0)

    # Conditions
    instrument_scope: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    market_regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    time_period: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Rationale
    ai_rationale: Mapped[str] = mapped_column(Text, default="")
    human_rationale: Mapped[str] = mapped_column(Text, default="")
    supporting_evidence: Mapped[str] = mapped_column(Text, default="")

    # Governance
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft")

    created_by: Mapped[str] = mapped_column(String(16), default="ai")


class TrialPlanORM(Base, TimestampMixin):
    """Pre-registered trial plan linked to a hypothesis."""

    __tablename__ = "trial_plans"
    __table_args__ = (
        Index("ix_tp_project", "research_project_id"),
        Index("ix_tp_hypothesis", "hypothesis_id"),
        Index("ix_tp_status", "status"),
    )

    trial_plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    research_project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    hypothesis_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Test design
    factor_combination: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    instruments: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    train_period_start: Mapped[str] = mapped_column(String(20), default="")
    train_period_end: Mapped[str] = mapped_column(String(20), default="")
    test_period_start: Mapped[str] = mapped_column(String(20), default="")
    test_period_end: Mapped[str] = mapped_column(String(20), default="")
    metric_name: Mapped[str] = mapped_column(String(32), default="sharpe_ratio")
    metric_threshold: Mapped[float] = mapped_column(Float, default=0.0)

    # Governance pre-registration
    trial_index_in_project: Mapped[int] = mapped_column(Integer, default=0)
    adjusted_alpha: Mapped[float] = mapped_column(Float, default=0.05)

    # Execution state
    status: Mapped[str] = mapped_column(String(16), default="planned")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob


class TrialResultORM(Base):
    """Trial execution result (embedded in trial_plans via result_json)."""

    __tablename__ = "trial_results"
    __table_args__ = (
        Index("ix_tr_trial", "trial_plan_id"),
    )

    trial_plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    metric_name: Mapped[str] = mapped_column(String(32), default="")
    is_significant: Mapped[int] = mapped_column(Integer, default=0)  # SQLite boolean
    adjusted_threshold: Mapped[float] = mapped_column(Float, default=0.0)
    raw_threshold: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    train_metric: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_metric: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
