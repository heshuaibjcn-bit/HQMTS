"""Admission domain model for paper-to-live transition (SAD 25)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import AdmissionStatus
from hqmts.core.types import AdmissionId
from hqmts.core.types import now_shanghai


class AdmissionRecord(BaseModel):
    """Paper-to-Live admission record.

    Tracks the full lifecycle: metrics collection, readiness evaluation,
    human approval, and final decision.
    """

    admission_id: AdmissionId
    strategy_instance_id: str
    strategy_version: str = ""
    paper_total_return_pct: float = 0.0
    paper_max_drawdown_pct: float = 0.0
    paper_sharpe_ratio: float = 0.0
    paper_win_rate_pct: float = 0.0
    paper_total_trades: int = 0
    paper_trading_days: int = 0
    max_daily_loss_pct: float = 0.0
    readiness_score: float = 0.0
    readiness_passed: bool = False
    status: AdmissionStatus = AdmissionStatus.PENDING_METRICS
    approval_request_id: str = ""
    approver: str = ""
    decision_reason: str = ""
    created_at: datetime = Field(default_factory=now_shanghai)
    decided_at: datetime | None = None

    model_config = {"frozen": False}  # Mutable for status transitions
