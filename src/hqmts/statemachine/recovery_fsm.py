"""Recovery session state machine (SAD 15.5).

States: created, loading_state, reconciling, rebuilding_context,
        pending_confirmation, completed, aborted, escalated

Agent role:
- Can generate recovery suggestions
- Can summarize exception chain
- Can assist with recovery report generation
- Cannot bypass pending_confirmation
"""

from __future__ import annotations

from hqmts.core.enums import RecoveryStatus
from hqmts.statemachine.base import StateMachine

RECOVERY_TRANSITIONS: dict[RecoveryStatus, set[RecoveryStatus]] = {
    RecoveryStatus.CREATED: {
        RecoveryStatus.LOADING_STATE,
        RecoveryStatus.ABORTED,
    },
    RecoveryStatus.LOADING_STATE: {
        RecoveryStatus.RECONCILING,
        RecoveryStatus.ESCALATED,
        RecoveryStatus.ABORTED,
    },
    RecoveryStatus.RECONCILING: {
        RecoveryStatus.REBUILDING_CONTEXT,
        RecoveryStatus.ESCALATED,
        RecoveryStatus.ABORTED,
    },
    RecoveryStatus.REBUILDING_CONTEXT: {
        RecoveryStatus.PENDING_CONFIRMATION,
        RecoveryStatus.ESCALATED,
        RecoveryStatus.ABORTED,
    },
    RecoveryStatus.PENDING_CONFIRMATION: {
        RecoveryStatus.COMPLETED,
        RecoveryStatus.ESCALATED,
        RecoveryStatus.ABORTED,
    },
    RecoveryStatus.COMPLETED: set(),  # Terminal
    RecoveryStatus.ABORTED: set(),  # Terminal
    RecoveryStatus.ESCALATED: {
        RecoveryStatus.PENDING_CONFIRMATION,
        RecoveryStatus.ABORTED,
    },
}

RECOVERY_TERMINAL_STATES: set[RecoveryStatus] = {
    RecoveryStatus.COMPLETED,
    RecoveryStatus.ABORTED,
}

recovery_fsm = StateMachine[RecoveryStatus](
    entity_type="Recovery",
    transitions=RECOVERY_TRANSITIONS,
    terminal_states=RECOVERY_TERMINAL_STATES,
)
