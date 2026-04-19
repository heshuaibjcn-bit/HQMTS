"""Instrument ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class InstrumentORM(Base, TimestampMixin):
    __tablename__ = "instruments"

    instrument_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    listing_status: Mapped[str] = mapped_column(String(4), default="L")
    board_type: Mapped[str] = mapped_column(String(16), default="main")
    is_st: Mapped[bool] = mapped_column(Boolean, default=False)
    lot_size: Mapped[int] = mapped_column(Integer, default=100)
    upper_limit_rule: Mapped[str] = mapped_column(String(16), default="normal")
    lower_limit_rule: Mapped[str] = mapped_column(String(16), default="normal")
    sector: Mapped[str] = mapped_column(String(32), default="")
    industry: Mapped[str] = mapped_column(String(32), default="")
    listing_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    delist_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_index: Mapped[bool] = mapped_column(Boolean, default=False)
    constituent_of: Mapped[str] = mapped_column(Text, default="")
