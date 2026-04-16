"""DecisionSnapshot ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class DecisionSnapshotORM(Base, TimestampMixin):
    __tablename__ = "decision_snapshots"
    __table_args__ = (
        Index(
            "ix_ds_strategy_decision_time",
            "strategy_instance_id",
            "decision_time",
        ),
        # Dedup: SAD 12.6 - strategy_instance_id + decision_time + bar_set_id
        Index(
            "ix_ds_dedup",
            "strategy_instance_id",
            "decision_time",
            "bar_set_id",
            unique=True,
        ),
    )

    decision_snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_instance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cycle: Mapped[str] = mapped_column(String(4), nullable=False)
    feature_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=True)
    bar_set_id: Mapped[str] = mapped_column(String(64), nullable=True)
    snapshot_completeness: Mapped[str] = mapped_column(String(20), default="complete")
    universe_scope_json: Mapped[str] = mapped_column(Text, default="[]")
    data_version: Mapped[str] = mapped_column(String(32), nullable=True)
    feature_version: Mapped[str] = mapped_column(String(32), nullable=True)
