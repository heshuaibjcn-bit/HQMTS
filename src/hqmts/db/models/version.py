"""VersionBinding ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class VersionBindingORM(Base, TimestampMixin):
    __tablename__ = "version_bindings"
    __table_args__ = (
        Index("ix_vb_entity", "entity_type", "entity_id"),
    )

    version_binding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    data_version: Mapped[str] = mapped_column(String(32), default="")
    feature_version: Mapped[str] = mapped_column(String(32), default="")
    strategy_version: Mapped[str] = mapped_column(String(32), default="")
    param_version: Mapped[str] = mapped_column(String(32), default="")
    risk_rule_version: Mapped[str] = mapped_column(String(32), default="")
    execution_policy_version: Mapped[str] = mapped_column(String(32), default="")
    engine_version: Mapped[str] = mapped_column(String(32), default="")
    qmt_adapter_version: Mapped[str] = mapped_column(String(32), default="")
    agent_workflow_version: Mapped[str] = mapped_column(String(32), default="")
    tool_version: Mapped[str] = mapped_column(String(32), default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    live_config_version: Mapped[str] = mapped_column(String(32), default="")
