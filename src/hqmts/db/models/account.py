"""Account ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class AccountORM(Base, TimestampMixin):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    total_asset: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    available_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    frozen_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    pnl_intraday: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    drawdown_intraday: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    risk_status: Mapped[str] = mapped_column(String(16), default="normal")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
