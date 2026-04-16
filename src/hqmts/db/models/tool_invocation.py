"""ToolInvocation ORM model (PRD 9.13, SAD 7.8)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ToolInvocationORM(Base, TimestampMixin):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        Index("ix_ti_task", "agent_task_id"),
        Index("ix_ti_tool_status", "tool_name", "status"),
        # Dedup: SAD 12.6 - agent_task_id + tool_name + idempotency_key
        Index(
            "ix_ti_dedup",
            "agent_task_id",
            "tool_name",
            "idempotency_key",
            unique=True,
        ),
    )

    invocation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(16), default="v1")
    input_digest: Mapped[str] = mapped_column(Text, default="")
    output_digest: Mapped[str] = mapped_column(Text, default="")
    side_effect_level: Mapped[str] = mapped_column(String(24), default="none")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error_code: Mapped[str] = mapped_column(String(32), default="")
    policy_check_id: Mapped[str] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=True)
    environment: Mapped[str] = mapped_column(String(16), default="research")
