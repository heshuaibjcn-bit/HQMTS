"""Position ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class PositionORM(Base, TimestampMixin):
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_account_instrument", "account_id", "instrument_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    total_quantity: Mapped[int] = mapped_column(default=0)
    available_quantity: Mapped[int] = mapped_column(default=0)
    frozen_quantity: Mapped[int] = mapped_column(default=0)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    last_update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
