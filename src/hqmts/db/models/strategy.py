"""Strategy and StrategyInstance ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class StrategyORM(Base, TimestampMixin):
    __tablename__ = "strategies"

    strategy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    supported_cycles: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    param_schema_json: Mapped[str] = mapped_column(Text, default="{}")
    default_params_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="draft")


class StrategyInstanceORM(Base, TimestampMixin):
    __tablename__ = "strategy_instances"

    strategy_instance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    instruments_json: Mapped[str] = mapped_column(Text, default="[]")
    account_id: Mapped[str] = mapped_column(String(32), nullable=True)
    cycle: Mapped[str] = mapped_column(String(4), default="5m")
    risk_config_override_json: Mapped[str] = mapped_column(Text, nullable=True)
