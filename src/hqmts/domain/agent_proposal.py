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
    policy_result: str = ""  # pass, fail, manual_review_required
    policy_check_id: PolicyCheckId | None = None
    approval_status: str = ""  # pending, approved, rejected, expired, canceled
    approval_request_id: str | None = None
    executed_result: str = ""  # Reference to execution result
    created_at: datetime

    def is_executable(self) -> bool:
        """Check if proposal has cleared all gates for execution."""
        return (
            self.policy_result == "pass"
            and self.approval_status in ("approved", "")  # Some proposals don't need approval
            and self.status_not_expired()
        )

    def requires_approval(self) -> bool:
        """Check if this proposal requires human approval."""
        return self.policy_result == "manual_review_required"

    def status_not_expired(self) -> bool:
        """Check proposal hasn't been rejected/expired/canceled."""
        return self.approval_status not in ("rejected", "expired", "canceled")
