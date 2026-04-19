"""ResearchProject domain model -- autonomous factor R&D workflow orchestrator.

6-stage lifecycle: Exploration → Hypothesis → Design → Execution → Validation → Report
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import ResearchMode, ResearchProjectStatus
from hqmts.core.types import ResearchProjectId


class ResearchProject(BaseModel):
    """A structured factor research project with governed lifecycle."""

    research_project_id: ResearchProjectId
    title: str
    research_question: str
    status: ResearchProjectStatus = ResearchProjectStatus.CREATED
    current_stage: str = "exploration"

    # Research scope
    instrument_ids: list[str] = Field(default_factory=list)
    factor_categories: list[str] = Field(default_factory=list)
    time_range_start: str = ""
    time_range_end: str = ""
    cycle: str = "1d"

    # Governance linkage
    governance_session_id: str = ""
    agent_task_id: str | None = None
    trial_budget: int = 100

    # Output references
    hypothesis_ids: list[str] = Field(default_factory=list)
    trial_ids: list[str] = Field(default_factory=list)
    report_id: str | None = None

    # Metadata
    created_by: str = ""
    mode: ResearchMode = ResearchMode.COLLABORATIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_terminal(self) -> bool:
        return self.status in (
            ResearchProjectStatus.COMPLETED,
            ResearchProjectStatus.FAILED,
            ResearchProjectStatus.CANCELED,
        )

    def to_dict(self) -> dict:
        return {
            "research_project_id": self.research_project_id,
            "title": self.title,
            "research_question": self.research_question,
            "status": self.status.value,
            "current_stage": self.current_stage,
            "instrument_ids": self.instrument_ids,
            "factor_categories": self.factor_categories,
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "cycle": self.cycle,
            "governance_session_id": self.governance_session_id,
            "agent_task_id": self.agent_task_id,
            "trial_budget": self.trial_budget,
            "hypothesis_ids": self.hypothesis_ids,
            "trial_ids": self.trial_ids,
            "report_id": self.report_id,
            "created_by": self.created_by,
            "mode": self.mode.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
