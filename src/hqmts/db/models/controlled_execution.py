"""ControlledExecution ORM model (SAD 7.10)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ControlledExecutionORM(Base, TimestampMixin):
    __tablename__ = "controlled_executions"
    __table_args__ = (
        Index("ix_ce_proposal", "source_proposal_id"),
        Index("ix_ce_target", "target_object_type", "target_object_id"),
        Index("ix_ce_status", "execution_status"),
    )

    controlled_execution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_proposal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_request_id: Mapped[str] = mapped_column(String(64), nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(16), default="pending")
    executed_by_service: Mapped[str] = mapped_column(String(64), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    result_ref: Mapped[str] = mapped_column(Text, default="")
    failure_reason: Mapped[str] = mapped_column(Text, default="")
