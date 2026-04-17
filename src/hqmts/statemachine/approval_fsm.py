"""ApprovalRequest state machine (SAD 15.8).

States: pending, approved, rejected, expired, canceled

Constraints:
- Terminal states: approved, rejected, expired, canceled
- Each approval request is deduplicated by source_type + source_id + approval_type
"""

from __future__ import annotations

from hqmts.core.enums import ApprovalStatus
from hqmts.statemachine.base import StateMachine

APPROVAL_TRANSITIONS: dict[ApprovalStatus, set[ApprovalStatus]] = {
    ApprovalStatus.PENDING: {
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.CANCELED,
    },
    ApprovalStatus.APPROVED: set(),  # Terminal
    ApprovalStatus.REJECTED: set(),  # Terminal
    ApprovalStatus.EXPIRED: set(),  # Terminal
    ApprovalStatus.CANCELED: set(),  # Terminal
}

APPROVAL_TERMINAL_STATES: set[ApprovalStatus] = {
    ApprovalStatus.APPROVED,
    ApprovalStatus.REJECTED,
    ApprovalStatus.EXPIRED,
    ApprovalStatus.CANCELED,
}

approval_fsm = StateMachine[ApprovalStatus](
    entity_type="ApprovalRequest",
    transitions=APPROVAL_TRANSITIONS,
    terminal_states=APPROVAL_TERMINAL_STATES,
)
