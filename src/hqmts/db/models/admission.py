"""Admission ORM model (SAD 25)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class AdmissionRecordORM(Base, TimestampMixin):
    __tablename__ = "admission_records"
    __table_args__ = (
        Index("ix_adm_strategy", "strategy_instance_id"),
        Index("ix_adm_status", "status"),
    )

    admission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_instance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), default="")
    paper_total_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    paper_max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    paper_sharpe_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    paper_win_rate_pct: Mapped[float] = mapped_column(Float, default=0.0)
    paper_total_trades: Mapped[int] = mapped_column(Integer, default=0)
    paper_trading_days: Mapped[int] = mapped_column(Integer, default=0)
    max_daily_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    readiness_passed: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_metrics")
    approval_request_id: Mapped[str] = mapped_column(String(64), default="")
    approver: Mapped[str] = mapped_column(String(64), default="")
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
