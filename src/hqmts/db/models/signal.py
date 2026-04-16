"""Signal ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class SignalORM(Base, TimestampMixin):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_strategy_decision_time", "strategy_instance_id", "decision_time"),
        Index("ix_signals_instrument", "instrument_id", "decision_time"),
    )

    signal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_instance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_direction: Mapped[str] = mapped_column(String(10), nullable=True)
    target_position: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=True)
    signal_strength: Mapped[float] = mapped_column(default=1.0)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), default="")
    feature_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=True)
    decision_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=True)
    cycle: Mapped[str] = mapped_column(String(4), default="5m")
