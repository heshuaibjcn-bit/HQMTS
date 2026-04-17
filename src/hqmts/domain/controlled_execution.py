"""ControlledExecution domain model (SAD 7.10).

Represents a deterministic execution triggered after Proposal/Approval flow.
Must be executed by a deterministic service, NOT by Agent Runtime.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import ExecutionStatus
from hqmts.core.types import ApprovalRequestId, ControlledExecutionId, ProposalId


class ControlledExecution(BaseModel):
    """Deterministic execution record for agent-initiated proposals.

    Constraints:
    - Must be executed by deterministic service
    - Agent Runtime must NOT directly write core state
    - Execution result must enter AuditEvent
    - Failure must trigger compensation or escalation
    """

    controlled_execution_id: ControlledExecutionId
    source_proposal_id: ProposalId
    approval_request_id: ApprovalRequestId | None = None
    action_type: str  # pause_open, close_only, correction, param_change, recovery, etc.
    target_object_type: str  # strategy_instance, risk_config, position
    target_object_id: str
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    executed_by_service: str = ""  # Name of the deterministic service that executed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_ref: str = ""  # Reference to execution result details
    failure_reason: str = ""

    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.execution_status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.EXPIRED,
        )

    def needs_escalation(self) -> bool:
        """Check if execution failed and needs human escalation."""
        return self.execution_status == ExecutionStatus.FAILED
