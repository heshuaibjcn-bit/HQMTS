"""Order ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class OrderORM(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_broker_order_id", "broker_order_id"),
        Index("ix_orders_account_status", "account_id", "status"),
        Index("ix_orders_instrument", "instrument_id", "created_at"),
    )

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_request_id: Mapped[str] = mapped_column(String(64), nullable=True)
    broker_order_id: Mapped[str] = mapped_column(String(64), nullable=True, unique=True)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), default="limit")
    signal_id: Mapped[str] = mapped_column(String(64), nullable=True)
    execution_intent_id: Mapped[str] = mapped_column(String(64), nullable=True)
    action_id: Mapped[str] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    submitted_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_quantity: Mapped[int] = mapped_column(default=0)
    avg_fill_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    reject_reason: Mapped[str] = mapped_column(Text, default="")
