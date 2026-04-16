"""AgentTask domain model (PRD 9.11, SAD 7.6).

Represents a single task initiated by a Hermes Agent.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import AgentRole, AgentTaskStatus, Environment
from hqmts.core.types import AgentTaskId, CorrelationId


class AgentTask(BaseModel):
    """Agent task with full lifecycle tracking.

    Constraints:
    - Every agent task must have a unique ID
    - Must record environment
    - Live-related tasks must bind workflow_version
    - AgentTask is NOT a production execution action
    """

    agent_task_id: AgentTaskId
    agent_role: AgentRole
    task_type: str  # research, backtest, analysis, report, reconciliation_analysis, etc.
    environment: Environment
    input_ref: str | None = None  # Reference to task input data
    output_ref: str | None = None  # Reference to task output data
    workflow_version: str = ""
    tool_plan: str = ""  # Planned tool calls (JSON)
    status: AgentTaskStatus = AgentTaskStatus.CREATED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str = ""
    triggered_by: str = ""  # user_id, schedule_id, system_event
    correlation_id: CorrelationId | None = None
    created_at: datetime

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (
            AgentTaskStatus.COMPLETED,
            AgentTaskStatus.FAILED,
            AgentTaskStatus.TIMEOUT,
            AgentTaskStatus.CANCELED,
        )

    def can_produce_proposals(self) -> bool:
        """Check if task is in a state that can produce proposals."""
        return self.status in (
            AgentTaskStatus.RUNNING,
            AgentTaskStatus.WAITING_TOOL,
        )
