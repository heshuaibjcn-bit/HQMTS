"""RiskCheckResult ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class RiskCheckResultORM(Base, TimestampMixin):
    __tablename__ = "risk_check_results"

    risk_check_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(64), nullable=True)
    order_request_id: Mapped[str] = mapped_column(String(64), nullable=True)
    result_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resized_quantity: Mapped[int] = mapped_column(Integer, nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    triggered_rules_json: Mapped[str] = mapped_column(Text, default="[]")
    check_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
