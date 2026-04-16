"""ExecutionIntent and OrderRequest ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class ExecutionIntentORM(Base, TimestampMixin):
    __tablename__ = "execution_intents"

    execution_intent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_instance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    target_quantity: Mapped[int] = mapped_column(nullable=False)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reservation_id: Mapped[str] = mapped_column(String(64), nullable=True)
    risk_check_id: Mapped[str] = mapped_column(String(64), nullable=True)


class OrderRequestORM(Base, TimestampMixin):
    __tablename__ = "order_requests"
    __table_args__ = (
        Index("ix_or_idempotency", "idempotency_key", unique=True),
    )

    order_request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(8), default="limit")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    tif: Mapped[str] = mapped_column(String(8), default="gtc")
    submit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_intent_id: Mapped[str] = mapped_column(String(64), nullable=True)
    reservation_id: Mapped[str] = mapped_column(String(64), nullable=True)
