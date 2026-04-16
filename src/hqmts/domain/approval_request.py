"""ApprovalRequest domain model (PRD 9.14, SAD 7.9).

Represents a request for human approval — results are immutable once decided.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import ApprovalStatus
from hqmts.core.types import ApprovalRequestId


class ApprovalRequest(BaseModel):
    """Human approval request for agent proposals or system changes.

    Constraints:
    - Must bind to a clear target object and action
    - Decision must be traceable to execution result
    - Decision is immutable once recorded
    - Approval does NOT equal execution success
    """

    approval_request_id: ApprovalRequestId
    source_type: str  # agent_proposal, system_event, manual_request
    source_id: str  # proposal_id or event_id
    approval_type: str  # live_deploy, risk_param_change, recovery, correction, etc.
    requested_by: str  # agent_role, user_id, system
    requested_at: datetime
    approver: str = ""
    approved_at: datetime | None = None
    decision: ApprovalStatus = ApprovalStatus.PENDING
    decision_reason: str = ""
    approval_snapshot_ref: str = ""  # Reference to the state snapshot at approval time
    expires_at: datetime | None = None

    def is_decided(self) -> bool:
        """Check if a decision has been made."""
        return self.decision != ApprovalStatus.PENDING

    def is_approved(self) -> bool:
        """Check if approved."""
        return self.decision == ApprovalStatus.APPROVED

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if the approval request has expired."""
        if self.expires_at is None:
            return False
        check_time = now or datetime.now()
        return check_time > self.expires_at
