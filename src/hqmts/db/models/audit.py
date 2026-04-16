"""AuditEvent ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base


class AuditEventORM(Base):
    """Append-only audit events. No updated_at — immutable."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_ae_entity", "entity_type", "entity_id"),
        Index("ix_ae_timestamp", "timestamp"),
        Index("ix_ae_correlation", "correlation_id"),
        Index("ix_ae_event_type", "event_type"),
    )

    audit_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    alert_level: Mapped[str] = mapped_column(String(4), default="P3")
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
