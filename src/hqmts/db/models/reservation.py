"""CashReservation ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class CashReservationORM(Base, TimestampMixin):
    __tablename__ = "cash_reservations"
    __table_args__ = (
        Index("ix_reservations_account_status", "account_id", "status"),
        # Dedup: SAD 12.6 - account_id + execution_intent_id
        Index("ix_reservations_dedup", "account_id", "execution_intent_id", unique=True),
    )

    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_instance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_id: Mapped[str] = mapped_column(String(64), nullable=True)
    execution_intent_id: Mapped[str] = mapped_column(String(64), nullable=True)
    reserved_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    consumed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_reason: Mapped[str] = mapped_column(Text, default="")
