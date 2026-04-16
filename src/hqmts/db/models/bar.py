"""Bar ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class BarORM(Base, TimestampMixin):
    __tablename__ = "bars"
    __table_args__ = (
        Index("ix_bars_instrument_cycle_time", "instrument_id", "cycle", "bar_end_time"),
        Index("ix_bars_instrument_cycle_version", "instrument_id", "cycle", "data_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    cycle: Mapped[str] = mapped_column(String(4), nullable=False)
    bar_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bar_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    data_version: Mapped[str] = mapped_column(String(32), nullable=False)
    quality: Mapped[str] = mapped_column(String(8), default="pass")
