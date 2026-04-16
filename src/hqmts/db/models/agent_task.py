"""AgentTask ORM model (PRD 9.11, SAD 7.6)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class AgentTaskORM(Base, TimestampMixin):
    __tablename__ = "agent_tasks"
    __table_args__ = (
        Index("ix_at_role_status", "agent_role", "status"),
        Index("ix_at_environment_status", "environment", "status"),
        Index("ix_at_correlation", "correlation_id"),
    )

    agent_task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_role: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    input_ref: Mapped[str] = mapped_column(Text, nullable=True)
    output_ref: Mapped[str] = mapped_column(Text, nullable=True)
    workflow_version: Mapped[str] = mapped_column(String(32), default="")
    tool_plan: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="created")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    triggered_by: Mapped[str] = mapped_column(String(64), default="")
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=True)
