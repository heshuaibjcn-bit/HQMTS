"""AgentProposal domain model (PRD 9.12, SAD 7.7).

Represents a structured suggestion from an Agent — NOT a final execution action.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import ProposalStatus
from hqmts.core.types import AgentTaskId, PolicyCheckId, ProposalId


class AgentProposal(BaseModel):
    """Agent proposal with full governance lifecycle.

    Constraints:
    - Proposal is NOT the final execution action
    - Must pass Policy Check before any execution
    - Live high-risk proposals must go through Approval
    - Expired proposals must not execute
    """

    proposal_id: ProposalId
    proposal_type: str  # pause_open, close_only, correction, risk_param_change, recovery_action, etc.
    source_agent_task_id: AgentTaskId
    target_object_type: str  # strategy_instance, risk_config, position, etc.
    target_object_id: str
    proposal_payload: str = "{}"  # JSON payload with proposal details
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: ProposalStatus = ProposalStatus.DRAFTED
    policy_result: str = ""  # pass, fail, manual_review_required — output of policy engine
    policy_check_id: PolicyCheckId | None = None
    approval_request_id: str | None = None
    executed_result: str = ""  # Reference to execution result
    created_at: datetime

    def is_executable(self) -> bool:
        """Check if proposal has cleared all gates for execution."""
        return self.status == ProposalStatus.APPROVED or (
            self.status == ProposalStatus.DRAFTED
            and self.policy_result == "pass"
        )

    def requires_approval(self) -> bool:
        """Check if this proposal requires human approval."""
        return self.status == ProposalStatus.PENDING_APPROVAL

    def status_not_expired(self) -> bool:
        """Check proposal hasn't reached a terminal rejection state."""
        return self.status not in (
            ProposalStatus.REJECTED,
            ProposalStatus.POLICY_REJECTED,
            ProposalStatus.EXPIRED,
            ProposalStatus.CANCELED,
        )
