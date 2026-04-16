"""ExternalManualEvent ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ExternalManualEventORM(Base, TimestampMixin):
    __tablename__ = "external_manual_events"
    __table_args__ = (
        Index("ix_eme_account_detected", "account_id", "detected_at"),
    )

    external_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    broker_order_id: Mapped[str] = mapped_column(String(64), nullable=True)
    broker_trade_id: Mapped[str] = mapped_column(String(64), nullable=True)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=True)
    side: Mapped[str] = mapped_column(String(8), nullable=True)
    quantity: Mapped[int] = mapped_column(nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_confidence: Mapped[str] = mapped_column(String(16), default="high")
    linked_internal_order_id: Mapped[str] = mapped_column(String(64), nullable=True)
    action_taken: Mapped[str] = mapped_column(Text, default="")
    audit_note: Mapped[str] = mapped_column(Text, default="")
