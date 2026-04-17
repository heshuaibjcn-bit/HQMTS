"""AgentProposal state machine (SAD 15.7).

States: drafted, policy_checking, policy_rejected, pending_approval, approved,
        rejected, execution_pending, executed, execution_failed, expired, canceled

Constraints:
- Terminal states: policy_rejected, rejected, executed, execution_failed, expired, canceled
- All Live proposals must pass policy checking before approval
"""

from __future__ import annotations

from hqmts.core.enums import ProposalStatus
from hqmts.statemachine.base import StateMachine

AGENT_PROPOSAL_TRANSITIONS: dict[ProposalStatus, set[ProposalStatus]] = {
    ProposalStatus.DRAFTED: {ProposalStatus.POLICY_CHECKING, ProposalStatus.CANCELED},
    ProposalStatus.POLICY_CHECKING: {
        ProposalStatus.POLICY_REJECTED,
        ProposalStatus.PENDING_APPROVAL,
        ProposalStatus.APPROVED,
        ProposalStatus.CANCELED,
    },
    ProposalStatus.POLICY_REJECTED: set(),  # Terminal
    ProposalStatus.PENDING_APPROVAL: {
        ProposalStatus.APPROVED,
        ProposalStatus.REJECTED,
        ProposalStatus.EXPIRED,
        ProposalStatus.CANCELED,
    },
    ProposalStatus.APPROVED: {ProposalStatus.EXECUTION_PENDING},
    ProposalStatus.REJECTED: set(),  # Terminal
    ProposalStatus.EXECUTION_PENDING: {
        ProposalStatus.EXECUTED,
        ProposalStatus.EXECUTION_FAILED,
        ProposalStatus.EXPIRED,
    },
    ProposalStatus.EXECUTED: set(),  # Terminal
    ProposalStatus.EXECUTION_FAILED: set(),  # Terminal
    ProposalStatus.EXPIRED: set(),  # Terminal
    ProposalStatus.CANCELED: set(),  # Terminal
}

AGENT_PROPOSAL_TERMINAL_STATES: set[ProposalStatus] = {
    ProposalStatus.POLICY_REJECTED,
    ProposalStatus.REJECTED,
    ProposalStatus.EXECUTED,
    ProposalStatus.EXECUTION_FAILED,
    ProposalStatus.EXPIRED,
    ProposalStatus.CANCELED,
}

agent_proposal_fsm = StateMachine[ProposalStatus](
    entity_type="AgentProposal",
    transitions=AGENT_PROPOSAL_TRANSITIONS,
    terminal_states=AGENT_PROPOSAL_TERMINAL_STATES,
)
