"""AgentProposal ORM model (PRD 9.12, SAD 7.7)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class AgentProposalORM(Base, TimestampMixin):
    __tablename__ = "agent_proposals"
    __table_args__ = (
        Index("ix_ap_task_status", "source_agent_task_id", "status"),
        Index("ix_ap_target", "target_object_type", "target_object_id"),
        # Dedup: SAD 12.6 - source_agent_task_id + proposal_type + target_object_id
        Index(
            "ix_ap_dedup",
            "source_agent_task_id",
            "proposal_type",
            "target_object_id",
            unique=True,
        ),
    )

    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    proposal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_agent_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_payload: Mapped[str] = mapped_column(Text, default="{}")
    confidence: Mapped[float] = mapped_column(default=0.0)
    policy_result: Mapped[str] = mapped_column(String(24), default="")
    policy_check_id: Mapped[str] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="drafted")
    approval_request_id: Mapped[str] = mapped_column(String(64), nullable=True)
    executed_result: Mapped[str] = mapped_column(Text, default="")
