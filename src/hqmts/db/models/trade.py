"""Trade ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class TradeORM(Base, TimestampMixin):
    __tablename__ = "trades"
    __table_args__ = (
        # Dedup: broker_trade_id (SAD 15.2)
        Index("ix_trades_broker_trade_id", "broker_trade_id", unique=True),
        Index("ix_trades_order", "order_id"),
    )

    trade_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    trade_quantity: Mapped[int] = mapped_column(nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    broker_trade_id: Mapped[str] = mapped_column(String(64), nullable=True)
