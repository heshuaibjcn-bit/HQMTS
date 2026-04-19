"""ReconciliationSession ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ReconciliationSessionORM(Base, TimestampMixin):
    __tablename__ = "reconciliation_sessions"

    reconciliation_session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_snapshot_ref: Mapped[str] = mapped_column(Text, nullable=True)
    broker_snapshot_ref: Mapped[str] = mapped_column(Text, nullable=True)
    diff_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    status: Mapped[str] = mapped_column(String(20), default="initialized")
    resolution_status: Mapped[str] = mapped_column(String(20), default="open")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
