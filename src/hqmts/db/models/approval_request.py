"""ApprovalRequest ORM model (PRD 9.14, SAD 7.9)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ApprovalRequestORM(Base, TimestampMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_ar_source", "source_type", "source_id"),
        Index("ix_ar_status", "decision"),
        # Dedup: SAD 12.6 - source_type + source_id + approval_type
        Index(
            "ix_ar_dedup",
            "source_type",
            "source_id",
            "approval_type",
            unique=True,
        ),
    )

    approval_request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_type: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approver: Mapped[str] = mapped_column(String(64), default="")
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str] = mapped_column(String(16), default="pending")
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    approval_snapshot_ref: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
