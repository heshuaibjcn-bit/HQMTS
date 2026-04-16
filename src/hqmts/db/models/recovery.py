"""RecoverySession ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class RecoverySessionORM(Base, TimestampMixin):
    __tablename__ = "recovery_sessions"

    recovery_session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(Text, default="")
    current_state_snapshot_ref: Mapped[str] = mapped_column(Text, nullable=True)
    proposed_actions_ref: Mapped[str] = mapped_column(Text, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="created")
    final_result: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
