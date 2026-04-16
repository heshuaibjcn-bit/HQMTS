"""Backtest result ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class BacktestResultORM(Base, TimestampMixin):
    __tablename__ = "backtest_results"
    __table_args__ = (
        Index("ix_backtest_strategy", "strategy_name", "strategy_version"),
        Index("ix_backtest_dates", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    backtest_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy_params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    instruments: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cycle: Mapped[str] = mapped_column(String(8), nullable=False)
    start_date: Mapped[str] = mapped_column(String(8), nullable=False)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    final_total_asset: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_return: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    annualized_return: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    sharpe_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    total_trades: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    profit_factor: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    trades: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    daily_values: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cost_summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    data_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
