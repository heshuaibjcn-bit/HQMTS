"""CorrectionEvent ORM model (SAD 10.4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class CorrectionEventORM(Base, TimestampMixin):
    __tablename__ = "correction_events"

    correction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    broker_trade_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(16), nullable=False)
    correction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    original_quantity: Mapped[int] = mapped_column(Integer, default=0)
    original_commission: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    corrected_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    corrected_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corrected_commission: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    reconciliation_session_id: Mapped[str] = mapped_column(String(64), default="")
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
