"""FeatureSnapshot ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class FeatureSnapshotORM(Base, TimestampMixin):
    __tablename__ = "feature_snapshots"
    __table_args__ = (
        Index("ix_fs_instrument_decision_time", "instrument_id", "decision_time"),
    )

    feature_snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cycle: Mapped[str] = mapped_column(String(4), nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_bar_versions_json: Mapped[str] = mapped_column(Text, nullable=False)
